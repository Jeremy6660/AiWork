"""三层审核 Agent：确定性规则、知识锚定、可选异构模型投票。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ..contracts import ContractError, validate_knowledge_item, validate_training_content
from knowledge_base.embedding import char_ngrams, normalize_text
from ..llm_client import LLMError, available_providers, call_llm_json


FACT_SIGNAL = re.compile(
    r"(M\d{2,3}|G\d{2,3}|mm|MPa|rpm|毫米|微米|不得|必须|禁止|用于|适合|应先|应确认)",
    re.IGNORECASE,
)
CITATION_PATTERN = re.compile(r"\[([A-Z0-9-]+)\]")
MODEL_PATTERN = re.compile(
    r"\b(?:[A-Za-z]+[- ]?\d{3,}|[A-Z]{2,}-[A-Z]{1,4}\d{1,4}|Fanuc\s+0i)\b",
    re.IGNORECASE,
)
STRUCTURED_TEACHING_FIELDS = {
    "学习目标",
    "适用条件",
    "教学步骤",
    "常见错误",
    "练习任务",
    "考核",
    "补学建议",
}
SAFETY_STEP_SIGNAL = re.compile(
    r"安全|急停|防护|联锁|不得|禁止|不启动|停止|上报"
)


def _has_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None and bool(value)


def _is_structured_microcourse(content: dict[str, Any]) -> bool:
    return any(field in content for field in STRUCTURED_TEACHING_FIELDS)


def _is_safety_critical_step(step: dict[str, Any]) -> bool:
    for field in ("安全关键", "安全关键步骤", "是否安全关键"):
        value = step.get(field)
        if value is True or (
            isinstance(value, str) and value.strip() in {"是", "true", "True"}
        ):
            return True
    text = " ".join(
        str(step.get(field, ""))
        for field in ("操作", "判定标准", "异常处理", "类型", "标签")
    )
    return bool(SAFETY_STEP_SIGNAL.search(text))


def _assessment_has_answer_or_rubric(assessment: dict[str, Any]) -> bool:
    if _has_content(assessment.get("标准答案")) or _has_content(
        assessment.get("评分规则")
    ):
        return True
    questions = assessment.get("题目", [])
    return isinstance(questions, list) and any(
        isinstance(question, dict) and _has_content(question.get("标准答案"))
        for question in questions
    )


def _find_model_mentions(content: dict[str, Any]) -> list[str]:
    body = re.sub(r"\[[^\]]+\]", "", str(content.get("正文", "")))
    step_texts: list[str] = []
    steps = content.get("教学步骤", [])
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_texts.extend(
                str(step.get(field, ""))
                for field in ("操作", "判定标准", "异常处理")
            )
    return list(dict.fromkeys(MODEL_PATTERN.findall("\n".join([body, *step_texts]))))


def _check_teaching_completeness(
    content: dict[str, Any],
) -> tuple[bool, list[str], dict[str, float]]:
    """以确定性规则检查结构化微课；旧式内容不启用本检查。"""

    if not _is_structured_microcourse(content):
        return True, [], {}

    problems: list[str] = []
    checks: list[bool] = []

    objectives = content.get("学习目标")
    objectives_passed = isinstance(objectives, list) and bool(objectives)
    if not objectives_passed:
        problems.append("学习目标不能为空")
    else:
        for index, objective in enumerate(objectives, 1):
            missing = [
                field
                for field in ("行为", "条件", "标准")
                if not isinstance(objective, dict)
                or not _has_content(objective.get(field))
            ]
            if missing:
                objectives_passed = False
                problems.append(
                    f"第{index}个学习目标缺少" + "、".join(missing)
                )
    checks.append(objectives_passed)

    steps = content.get("教学步骤")
    valid_steps = steps if isinstance(steps, list) else []
    step_count_passed = len(valid_steps) >= 4
    if not step_count_passed:
        problems.append("教学步骤少于4条")
    checks.append(step_count_passed)

    step_judgement_passed = bool(valid_steps)
    determinable_steps = 0
    for index, step in enumerate(valid_steps, 1):
        if not isinstance(step, dict):
            step_judgement_passed = False
            problems.append(f"第{index}个教学步骤格式不正确")
            continue
        has_standard = _has_content(step.get("判定标准"))
        has_exception = _has_content(step.get("异常处理"))
        if has_standard or has_exception:
            determinable_steps += 1
        if not has_standard and not has_exception:
            step_judgement_passed = False
            problems.append(f"第{index}个教学步骤缺少判定标准或异常处理")
        elif _is_safety_critical_step(step):
            if not has_standard:
                step_judgement_passed = False
                problems.append(f"第{index}个教学步骤缺少判定标准")
            if not has_exception:
                step_judgement_passed = False
                problems.append(f"第{index}个教学步骤缺少异常处理")
    checks.append(step_judgement_passed)

    step_citations_passed = bool(valid_steps)
    for index, step in enumerate(valid_steps, 1):
        references = step.get("引用知识ID") if isinstance(step, dict) else None
        if not isinstance(references, list) or not references or not all(
            isinstance(reference, str) and reference.strip()
            for reference in references
        ):
            step_citations_passed = False
            problems.append(f"第{index}个教学步骤缺少引用知识ID")
    checks.append(step_citations_passed)

    practice_passed = _has_content(content.get("练习任务"))
    if not practice_passed:
        problems.append("练习任务不能为空")
    checks.append(practice_passed)

    assessment = content.get("考核")
    assessment_dict = assessment if isinstance(assessment, dict) else {}
    questions = assessment_dict.get("题目")
    assessment_passed = True
    if not isinstance(questions, list) or len(questions) < 2:
        assessment_passed = False
        problems.append("考核题目少于2题")
    if not _assessment_has_answer_or_rubric(assessment_dict):
        assessment_passed = False
        problems.append("考核缺少标准答案或评分规则")
    if not _has_content(assessment_dict.get("合格线")):
        assessment_passed = False
        problems.append("考核缺少合格线")
    checks.append(assessment_passed)

    mapping_passed = bool(assessment_dict)
    if not mapping_passed:
        problems.append("考核为空，无法映射到学习目标")
    checks.append(mapping_passed)

    applicability = content.get("适用条件")
    equipment = applicability.get("设备") if isinstance(applicability, dict) else None
    equipment_text = str(equipment)
    equipment_unknown = "未指定" in equipment_text or "未知" in equipment_text
    model_mentions = _find_model_mentions(content) if equipment_unknown else []
    model_boundary_passed = not model_mentions
    if not model_boundary_passed:
        problems.append(
            "设备型号未知时不得出现型号专属参数：" + "、".join(model_mentions)
        )
    checks.append(model_boundary_passed)

    remedial_passed = _has_content(content.get("补学建议"))
    if not remedial_passed:
        problems.append("补学建议不能为空")
    checks.append(remedial_passed)

    metrics = {
        "教学完整率": round(sum(checks) / len(checks), 4),
        "目标考核对齐率": float(bool(objectives) and bool(assessment_dict)),
        "关键步骤可判定率": round(
            determinable_steps / len(valid_steps), 4
        )
        if valid_steps
        else 0.0,
    }
    return all(checks), problems, metrics


def _merge_teaching_review(
    fact_result: dict[str, Any],
    teaching_enabled: bool,
    teaching_passed: bool,
    teaching_problems: list[str],
    teaching_metrics: dict[str, float],
) -> dict[str, Any]:
    """在不改变事实审核分数和明细的前提下合并教学审核结果。"""

    fact_result["事实审核"] = "pass" if fact_result.get("通过") else "fail"
    fact_result["教学完整性"] = (
        "未启用" if not teaching_enabled else "pass" if teaching_passed else "fail"
    )
    fact_result["教学问题"] = list(teaching_problems)
    fact_result["教学完整率"] = teaching_metrics.get("教学完整率", 1.0)
    fact_result["目标考核对齐率"] = teaching_metrics.get("目标考核对齐率", 1.0)
    fact_result["关键步骤可判定率"] = teaching_metrics.get("关键步骤可判定率", 1.0)

    if teaching_enabled and not teaching_passed:
        fact_result["通过"] = False
        fact_result["流程状态"] = "失败"
        teaching_advice = "教学不完整：" + "；".join(teaching_problems)
        existing_advice = str(fact_result.get("修改建议", "")).strip()
        fact_result["修改建议"] = (
            existing_advice + "；" + teaching_advice
            if existing_advice
            else teaching_advice
        )
    return fact_result


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


def _taskpkg_anchors(taskpkg: dict[str, Any]) -> list[tuple[str, str, list[str]]]:
    """从任务包提取（字段前缀, 字段值, 引用知识ID）三元组，供任务包锚定。

    任务包是已核验的可信中间层，生成器只原样渲染任务包字段。
    断言文本若来自任务包字段，锚定依据就是任务包字段本身。
    """

    anchors: list[tuple[str, str, list[str]]] = []

    def add(prefix: str, value: Any, refs: Any) -> None:
        if isinstance(value, str) and value.strip() and isinstance(refs, list) and refs:
            anchors.append((prefix, value.strip(), [str(r) for r in refs]))

    for objective in taskpkg.get("学习目标", []):
        if not isinstance(objective, dict):
            continue
        refs = objective.get("引用知识ID", [])
        for field in ("行为", "条件", "标准"):
            add("学习目标", objective.get(field), refs)

    for step in taskpkg.get("操作步骤", []):
        if not isinstance(step, dict):
            continue
        refs = step.get("引用知识ID", [])
        for field in ("操作", "判定标准", "异常处理"):
            add("操作步骤", step.get(field), refs)

    for error in taskpkg.get("常见错误", []):
        if not isinstance(error, dict):
            continue
        refs = error.get("引用知识ID", [])
        for field in ("错误", "后果", "纠正"):
            add("常见错误", error.get(field), refs)

    assessment = taskpkg.get("考核", {})
    if isinstance(assessment, dict):
        question_refs: list[str] = []
        for question in assessment.get("题目", []):
            if isinstance(question, dict):
                q_refs = question.get("引用知识ID", [])
                if isinstance(q_refs, list):
                    question_refs.extend(str(r) for r in q_refs)
                add("考核题目", question.get("题目"), q_refs)
        assessment_refs = assessment.get("引用知识ID", [])
        if not assessment_refs:
            # 渲染层合格线引用汇总自题目引用，锚点同样汇总
            assessment_refs = question_refs
        add("考核合格线", assessment.get("合格线"), assessment_refs)
        for remedial in assessment.get("错后补学", []):
            if isinstance(remedial, dict):
                add("错后补学", remedial.get("补学内容"), remedial.get("引用知识ID", []))

    practice = taskpkg.get("练习任务", {})
    if isinstance(practice, dict):
        add("练习任务", practice.get("任务"), taskpkg.get("练习任务引用", []))

    return anchors


def _taskpkg_anchor_claim(
    claim_text: str,
    claim_ids: list[str],
    anchors: list[tuple[str, str, list[str]]],
) -> dict[str, Any] | None:
    """尝试用任务包字段锚定一条断言。

    匹配规则：断言文本包含任务包字段值，且断言引用的知识ID是任务包字段引用的子集。
    返回 None 表示任务包锚定不适用（需回退知识相似度锚定）。
    """

    for prefix, value, refs in anchors:
        if value in claim_text:
            matched = True
        else:
            # 渲染层可能给字段加了引导前缀（如"合格线：""判定标准：""异常处理："），
            # 剥离常见前缀后再匹配。
            stripped = claim_text
            for lead in ("合格线：", "判定标准：", "异常处理：", "任务：", "操作：", "错误：", "后果：", "纠正："):
                if stripped.startswith(lead):
                    stripped = stripped[len(lead):]
                    break
            matched = value in stripped
        if not matched:
            continue
        if set(claim_ids) and not set(claim_ids).issubset(set(refs)):
            return {
                "状态": "无依据",
                "依据": (
                    f"断言文本来自任务包“{prefix}”字段，但引用的知识ID"
                    f"（{'、'.join(claim_ids)}）与任务包字段引用（{'、'.join(refs)}）不一致"
                ),
                "相似度": 0.0,
            }
        return {
            "状态": "有依据",
            "依据": f"任务包“{prefix}”字段（引用：{'、'.join(refs)}）",
            "相似度": 1.0,
        }
    return None


def _deterministic_anchor(
    content: dict[str, Any],
    knowledge: list[dict[str, Any]],
    taskpkg: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_id = {item["知识ID"]: item for item in knowledge}
    anchors = _taskpkg_anchors(taskpkg) if taskpkg else []
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
        if anchors:
            anchored = _taskpkg_anchor_claim(
                claim["断言"], claim["引用知识ID"], anchors
            )
            if anchored is not None:
                results.append({**claim, **anchored})
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


def review_content(
    培训内容: dict[str, Any],
    知识列表: list[dict[str, Any]],
    *,
    任务包: dict[str, Any] | None = None,
) -> dict[str, Any]:
    teaching_enabled = _is_structured_microcourse(培训内容)
    teaching_passed, teaching_problems, teaching_metrics = (
        _check_teaching_completeness(培训内容)
    )
    if not isinstance(知识列表, list) or not 知识列表:
        return _merge_teaching_review({
            "通过": False,
            "流程状态": "失败",
            "幻觉分数": 1.0,
            "修改建议": "知识列表为空，不能进行事实审核或发布内容。",
            "审核明细": {"规则引擎": "fail", "风险等级": "high", "投票明细": []},
            "断言核查": [],
        }, teaching_enabled, teaching_passed, teaching_problems, teaching_metrics)
    for item in 知识列表:
        validate_knowledge_item(item)

    rule_passed, rule_problems = _check_rules(培训内容, 知识列表)
    if not rule_passed:
        return _merge_teaching_review({
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
        }, teaching_enabled, teaching_passed, teaching_problems, teaching_metrics)

    checks = _deterministic_anchor(培训内容, 知识列表, 任务包)
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
    l3_triggered = False
    flow_status = "通过" if not invalid else "失败"
    passed = not invalid
    if hallucination_score > 0.2 and os.getenv("ENABLE_L3_VOTING", "0") == "1":
        l3_triggered = True
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
    if not l3_triggered:
        vote_status = "未触发"
    elif available_votes == 0:
        reason = "无可用供应商" if not votes else "供应商调用均失败"
        vote_status = f"已触发：0/0（{reason}）"
    elif available_votes < 2:
        vote_status = f"已触发：{passed_votes}/{available_votes}（可用独立供应商不足两个）"
    else:
        vote_status = f"已触发：{passed_votes}/{available_votes}"
    return _merge_teaching_review({
        "通过": passed,
        "流程状态": flow_status,
        "幻觉分数": hallucination_score,
        "修改建议": advice,
        "审核明细": {
            "规则引擎": "pass",
            "知识锚定": f"{l2_mode}: {total - len(invalid)}/{total} 条有依据",
            "模型投票": vote_status,
            "风险等级": risk,
            "投票明细": votes,
        },
        "断言核查": checks,
    }, teaching_enabled, teaching_passed, teaching_problems, teaching_metrics)


if __name__ == "__main__":
    from .generator import generate_content
    from .profile import build_profile
    from .retrieval import search_knowledge

    question = "M代码编程"
    knowledge = search_knowledge(question)
    content = generate_content(build_profile("数控机床操作工"), knowledge, question)
    print(json.dumps(review_content(content, knowledge), ensure_ascii=False, indent=2))
