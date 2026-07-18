"""三层审核 Agent：确定性规则、知识锚定、可选异构模型投票。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from contracts import ContractError, validate_knowledge_item, validate_training_content
from knowledge_base.embedding import char_ngrams, normalize_text
from llm_client import LLMError, available_providers, call_llm_json


FACT_SIGNAL = re.compile(
    r"(M\d{2,3}|G\d{2,3}|mm|MPa|rpm|毫米|微米|不得|必须|禁止|用于|适合|应先|应确认)",
    re.IGNORECASE,
)
CITATION_PATTERN = re.compile(r"\[([A-Z0-9-]+)\]")


def _check_rules(content: dict[str, Any], knowledge: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    try:
        validate_training_content(content)
    except ContractError as exc:
        return False, [str(exc)]
    if len(content["正文"].strip()) < 80:
        problems.append("正文少于 80 个字符")

    knowledge_ids = {item["知识ID"] for item in knowledge}
    declared = set(content["引用知识ID"])
    inline = set(CITATION_PATTERN.findall(content["正文"]))
    if declared - knowledge_ids:
        problems.append("声明了知识列表之外的引用：" + "、".join(sorted(declared - knowledge_ids)))
    if inline - knowledge_ids:
        problems.append("正文引用了知识列表之外的 ID：" + "、".join(sorted(inline - knowledge_ids)))
    if not inline:
        problems.append("正文没有行内知识ID引用")
    if inline - declared:
        problems.append("正文行内引用未写入“引用知识ID”字段")

    for word in ["大概", "差不多", "随便", "无所谓", "据我所知"]:
        if word in content["正文"]:
            problems.append(f"包含不确定或低质量表达：{word}")

    for line_number, line in enumerate(content["正文"].splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if FACT_SIGNAL.search(stripped) and not CITATION_PATTERN.search(stripped):
            problems.append(f"第 {line_number} 行疑似事实断言但没有知识ID引用")
    return not problems, problems


def _text_similarity(left: str, right: str) -> float:
    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_right in normalized_left or normalized_left in normalized_right:
        return 1.0
    left_grams = set(char_ngrams(left, (2,)))
    right_grams = set(char_ngrams(right, (2,)))
    union = left_grams | right_grams
    return len(left_grams & right_grams) / len(union) if union else 0.0


def _extract_claims(content: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for line in content["正文"].splitlines():
        ids = CITATION_PATTERN.findall(line)
        if not ids:
            continue
        text = CITATION_PATTERN.sub("", line).lstrip("- 0123456789.、").strip()
        if text:
            claims.append({"断言": text, "引用知识ID": ids})
    return claims


def _deterministic_anchor(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {item["知识ID"]: item for item in knowledge}
    results: list[dict[str, Any]] = []
    for claim in _extract_claims(content):
        invalid_ids = [item for item in claim["引用知识ID"] if item not in by_id]
        if invalid_ids:
            results.append(
                {
                    **claim,
                    "状态": "无依据",
                    "依据": "引用ID不存在：" + "、".join(invalid_ids),
                    "相似度": 0.0,
                }
            )
            continue
        similarities = [
            _text_similarity(claim["断言"], by_id[item]["内容"])
            for item in claim["引用知识ID"]
        ]
        best = max(similarities, default=0.0)
        status = "有依据" if best >= 0.45 else "无依据"
        results.append(
            {
                **claim,
                "状态": status,
                "依据": "、".join(claim["引用知识ID"]),
                "相似度": round(best, 4),
            }
        )
    return results


def _llm_anchor(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prompt = {
        "任务": "逐条核查培训内容中的事实断言",
        "唯一可信知识": [
            {"知识ID": item["知识ID"], "内容": item["内容"]} for item in knowledge
        ],
        "培训正文": content["正文"],
        "输出格式": {
            "断言核查": [
                {
                    "断言": "原句",
                    "状态": "有依据|无依据|矛盾",
                    "依据": "知识ID或原因",
                }
            ]
        },
    }
    response = call_llm_json(
        "deepseek",
        [
            {"role": "system", "content": "你是严格的制造业事实核查 Agent，只输出 JSON。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    )
    checks = response.get("断言核查")
    if not isinstance(checks, list) or not checks:
        raise LLMError("L2 未返回有效的“断言核查”列表")
    normalized: list[dict[str, Any]] = []
    for item in checks:
        if not isinstance(item, dict) or item.get("状态") not in {"有依据", "无依据", "矛盾"}:
            raise LLMError("L2 断言核查字段不合法")
        normalized.append(
            {
                "断言": str(item.get("断言", "")),
                "状态": item["状态"],
                "依据": str(item.get("依据", "")),
                "模型": response.get("_模型", "deepseek"),
            }
        )
    return normalized


def _model_vote(
    content: dict[str, Any], knowledge: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prompt = json.dumps(
        {
            "任务": "判断培训内容是否完全受知识列表支持",
            "知识列表": [
                {"知识ID": item["知识ID"], "内容": item["内容"]} for item in knowledge
            ],
            "培训内容": content,
            "输出": {"通过": True, "理由": "具体理由"},
        },
        ensure_ascii=False,
    )
    votes: list[dict[str, Any]] = []
    for provider in available_providers():
        try:
            response = call_llm_json(
                provider,
                [
                    {"role": "system", "content": "你是独立审核员，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
            )
            passed = response.get("通过")
            if not isinstance(passed, bool):
                raise LLMError("投票结果缺少布尔字段“通过”")
            votes.append(
                {
                    "模型": provider,
                    "通过": passed,
                    "理由": str(response.get("理由", "未提供理由")),
                }
            )
        except LLMError as exc:
            votes.append({"模型": provider, "通过": None, "理由": str(exc)})
    return votes


def review_content(培训内容: dict[str, Any], 知识列表: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(知识列表, list) or not 知识列表:
        return {
            "通过": False,
            "流程状态": "失败",
            "幻觉分数": 1.0,
            "修改建议": "知识列表为空，不能进行事实审核或发布内容。",
            "审核明细": {"规则引擎": "fail", "风险等级": "high", "投票明细": []},
            "断言核查": [],
        }
    for item in 知识列表:
        validate_knowledge_item(item)

    rule_passed, rule_problems = _check_rules(培训内容, 知识列表)
    if not rule_passed:
        return {
            "通过": False,
            "流程状态": "失败",
            "幻觉分数": 1.0,
            "修改建议": "；".join(rule_problems),
            "审核明细": {
                "规则引擎": "fail",
                "规则问题": rule_problems,
                "知识锚定": "未执行",
                "模型投票": "未触发",
                "风险等级": "high",
                "投票明细": [],
            },
            "断言核查": [],
        }

    checks = _deterministic_anchor(培训内容, 知识列表)
    l2_mode = "deterministic"
    if os.getenv("ENABLE_LLM_REVIEW", "0") == "1" and "deepseek" in available_providers():
        try:
            checks = _llm_anchor(培训内容, 知识列表)
            l2_mode = "deepseek"
        except LLMError:
            l2_mode = "deterministic-fallback"

    total = len(checks)
    invalid = [item for item in checks if item["状态"] in {"无依据", "矛盾"}]
    hallucination_score = round(len(invalid) / total, 4) if total else 1.0
    risk = "low" if hallucination_score <= 0.05 else "medium" if hallucination_score <= 0.2 else "high"

    votes: list[dict[str, Any]] = []
    flow_status = "通过" if not invalid else "失败"
    passed = not invalid
    if hallucination_score > 0.2 and os.getenv("ENABLE_L3_VOTING", "0") == "1":
        votes = _model_vote(培训内容, 知识列表)
        successful = [vote for vote in votes if isinstance(vote.get("通过"), bool)]
        if len(successful) < 2:
            flow_status = "需人工复核"
            passed = False
        else:
            passed_count = sum(1 for vote in successful if vote["通过"])
            passed = passed_count >= 2
            flow_status = "通过" if passed else "失败"

    advice = ""
    if invalid:
        advice = "请删除或改写以下无依据/矛盾断言：" + "；".join(
            item["断言"] for item in invalid[:5]
        )
    if flow_status == "需人工复核":
        advice = (advice + "；" if advice else "") + "可用独立模型不足两个，必须人工复核"

    passed_votes = sum(1 for vote in votes if vote.get("通过") is True)
    available_votes = sum(1 for vote in votes if isinstance(vote.get("通过"), bool))
    return {
        "通过": passed,
        "流程状态": flow_status,
        "幻觉分数": hallucination_score,
        "修改建议": advice,
        "审核明细": {
            "规则引擎": "pass",
            "知识锚定": f"{l2_mode}: {total - len(invalid)}/{total} 条有依据",
            "模型投票": f"{passed_votes}/{available_votes}" if votes else "未触发",
            "风险等级": risk,
            "投票明细": votes,
        },
        "断言核查": checks,
    }


if __name__ == "__main__":
    from agents.generator import generate_content
    from agents.profile import build_profile
    from agents.retrieval import search_knowledge

    question = "M代码编程"
    knowledge = search_knowledge(question)
    content = generate_content(build_profile("数控机床操作工"), knowledge, question)
    print(json.dumps(review_content(content, knowledge), ensure_ascii=False, indent=2))
