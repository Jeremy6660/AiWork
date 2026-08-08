"""智策育训 Orchestrator：可信状态机与可审计的生成—审核闭环。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from .agents.evaluator import evaluate
from .agents.generator import KnowledgeNotCoveredError, generate_content
from .agents.profile import apply_feedback, build_profile, get_stable_positions
from .agents.retrieval import _load_items, search_knowledge, search_training_task
from .agents.reviewer import review_content


MAX_REGENERATIONS = 2
ProgressCallback = Callable[[str], None]


def _load_task_knowledge(taskpkg: dict[str, Any]) -> list[dict[str, Any]]:
    """按任务包知识 ID 精确加载已验证知识，并保留任务包中的顺序。"""

    verified_items = _load_items()
    knowledge: list[dict[str, Any]] = []
    for knowledge_id in taskpkg.get("知识ID", []):
        item = verified_items.get(knowledge_id)
        if item is not None and item.get("验证状态") == "已验证":
            knowledge.append({**item, "检索分数": 1.0})
    return knowledge


def _empty_evaluation(reason: str) -> dict[str, Any]:
    return {
        "事实性": 0.0,
        "专业性": 0.0,
        "可读性": 0.0,
        "匹配度": 0.0,
        "知识覆盖率": 0.0,
        "综合分": 0.0,
        "优化建议": reason,
        "指标依据": {},
    }


def run(
    岗位: str,
    答题记录: list[dict[str, Any]] | None = None,
    question: str = "",
    *,
    学习场景: dict[str, Any] | None = None,
    反馈模式: str = "",
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    if not isinstance(岗位, str) or not 岗位.strip():
        raise ValueError("岗位必须是非空字符串")
    if 答题记录 is None:
        答题记录 = []
    if not isinstance(答题记录, list):
        raise ValueError("答题记录必须是列表")
    if not isinstance(question, str):
        raise ValueError("question 必须是字符串")
    topic = question.strip() or f"{岗位}核心技能培训"

    logs: list[str] = []
    iterations: list[dict[str, Any]] = []
    started = time.time()

    def log(message: str) -> None:
        line = f"[{time.time() - started:.2f}s] {message}"
        logs.append(line)
        if progress_callback:
            progress_callback(line)

    profile: dict[str, Any] = {}
    knowledge: list[dict[str, Any]] = []
    content: dict[str, Any] = {}
    review: dict[str, Any] = {}
    taskpkg: dict[str, Any] | None = None
    generation_taskpkg: dict[str, Any] | None = None
    taskpkg_hint = ""
    regeneration_count = 0

    try:
        log(f"👤 画像 Agent：构建“{岗位}”画像")
        profile = build_profile(岗位, 答题记录, 学习场景)
        if 反馈模式:
            profile = apply_feedback(profile, 反馈模式)
        log(
            "   目标技能=" + "、".join(profile["目标技能"])
            + f"，推荐难度={profile['推荐难度']}"
        )
        if 岗位 not in get_stable_positions():
            message = "该岗位仍处于实验阶段，尚无完成核验的知识证据"
            log(f"⛔ {message}")
            return {
                "流程状态": "失败",
                "失败原因": message,
                "画像": profile,
                "知识列表": [],
                "培训内容": {},
                "审核明细": {"规则引擎": "未执行", "风险等级": "high"},
                "审核通过": False,
                "幻觉分数": 1.0,
                "评估结果": _empty_evaluation(message),
                "重试次数": 0,
                "学习路径": profile.get("学习路径", []),
                "迭代历史": [],
                "协同日志": logs,
                "任务包": None,
                "任务包提示": "",
            }

        if question.strip():
            taskpkg = search_training_task(岗位, question.strip())
        taskpkg_status = taskpkg.get("验证状态") if taskpkg is not None else None
        allow_draft_taskpkg = (
            taskpkg_status == "草稿" and os.getenv("ALLOW_DRAFT_TASKPKG") == "1"
        )
        if taskpkg is not None and (
            taskpkg_status == "已核验" or allow_draft_taskpkg
        ):
            generation_taskpkg = taskpkg
            if allow_draft_taskpkg:
                taskpkg_hint = "非正式（草稿任务包）：仅供离线盲测和调试"
                log(f"⚠️ 任务包检索：调试放行草稿任务包“{taskpkg['任务名称']}”")
            else:
                log(f"📦 任务包检索：命中已核验任务包“{taskpkg['任务名称']}”")
            knowledge = _load_task_knowledge(taskpkg)
            log(
                "   按任务包加载已验证知识="
                + "、".join(item["知识ID"] for item in knowledge)
            )
        else:
            if taskpkg is not None and taskpkg.get("验证状态") == "草稿":
                taskpkg_hint = (
                    "当前可提供知识说明，但该任务包尚未完成专业核验，"
                    "不能生成完整培训微课"
                )
                log(f"⚠️ 任务包检索：命中草稿任务包“{taskpkg['任务名称']}”")
            log(f"🔍 检索 Agent：检索主题“{topic}”")
            knowledge = search_knowledge(topic)
        if not knowledge:
            message = "知识库未覆盖该主题，系统拒绝生成专业内容"
            log(f"⛔ {message}")
            return {
                "流程状态": "失败",
                "失败原因": message,
                "画像": profile,
                "知识列表": [],
                "培训内容": {},
                "审核明细": {"规则引擎": "未执行", "风险等级": "high"},
                "审核通过": False,
                "幻觉分数": 1.0,
                "评估结果": _empty_evaluation(message),
                "重试次数": 0,
                "学习路径": profile.get("学习路径", []),
                "迭代历史": [],
                "协同日志": logs,
                "任务包": taskpkg,
                "任务包提示": taskpkg_hint,
            }
        if generation_taskpkg is None:
            log(
                "   命中知识="
                + "、".join(
                    f"{item['知识ID']}({item['检索分数']:.2f})"
                    for item in knowledge
                )
            )

        advice = ""
        for round_number in range(1, MAX_REGENERATIONS + 2):
            log(f"📝 生成 Agent：第 {round_number} 轮生成")
            content = generate_content(
                profile,
                knowledge,
                topic,
                advice,
                任务包=generation_taskpkg,
            )
            log(f"   类型={content['类型']}，模式={content['生成模式']}")

            log(f"🔎 审核 Agent：第 {round_number} 轮审核")
            review = review_content(content, knowledge, 任务包=generation_taskpkg)
            iterations.append(
                {
                    "轮次": round_number,
                    "内容标题": content["标题"],
                    "正文": content["正文"],
                    "资源类型": content["类型"],
                    "生成模式": content["生成模式"],
                    "流程状态": review["流程状态"],
                    "审核通过": review["通过"],
                    "幻觉分数": review["幻觉分数"],
                    "修改建议": review["修改建议"],
                    "断言核查": review.get("断言核查", []),
                    "事实审核": review.get("事实审核"),
                    "教学完整性": review.get("教学完整性"),
                    "教学问题": review.get("教学问题", []),
                }
            )
            log(
                f"   状态={review['流程状态']}，"
                f"幻觉分数={review['幻觉分数']:.2%}"
            )
            if review["通过"]:
                log("✅ 审核通过")
                break
            if regeneration_count >= MAX_REGENERATIONS:
                log("⚠️ 已达到重新生成上限，内容不得自动发布，转人工复核")
                review["流程状态"] = "需人工复核"
                break
            regeneration_count += 1
            advice = review["修改建议"] or "删除无依据陈述并严格使用知识ID引用"
            log(f"🔄 根据具体审核意见重新生成：{advice}")

        log("📊 评估模块：计算单份内容可解释指标")
        evaluation = evaluate(content, knowledge, profile)
        final_status = review.get("流程状态", "失败")
        log(f"🏁 流程完成：{final_status}，综合分={evaluation['综合分']:.2%}")
        return {
            "流程状态": final_status,
            "失败原因": "" if final_status == "通过" else review.get("修改建议", ""),
            "画像": profile,
            "知识列表": knowledge,
            "培训内容": content,
            "审核明细": review.get("审核明细", {}),
            "断言核查": review.get("断言核查", []),
            "审核通过": bool(review.get("通过", False)),
            "幻觉分数": float(review.get("幻觉分数", 1.0)),
            "评估结果": evaluation,
            "重试次数": regeneration_count,
            "学习路径": profile.get("学习路径", []),
            "迭代历史": iterations,
            "协同日志": logs,
            "任务包": taskpkg,
            "任务包提示": taskpkg_hint,
            "事实审核": review.get("事实审核"),
            "教学完整性": review.get("教学完整性"),
            "教学问题": review.get("教学问题", []),
            "教学完整率": review.get("教学完整率"),
            "目标考核对齐率": review.get("目标考核对齐率"),
            "关键步骤可判定率": review.get("关键步骤可判定率"),
        }
    except (KnowledgeNotCoveredError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        log(f"❌ 流程异常：{message}")
        return {
            "流程状态": "失败",
            "失败原因": message,
            "画像": profile,
            "知识列表": knowledge,
            "培训内容": content,
            "审核明细": review.get("审核明细", {"规则引擎": "未完成", "风险等级": "high"}),
            "断言核查": review.get("断言核查", []),
            "审核通过": False,
            "幻觉分数": 1.0,
            "评估结果": _empty_evaluation(message),
            "重试次数": regeneration_count,
            "学习路径": profile.get("学习路径", []) if profile else [],
            "迭代历史": iterations,
            "协同日志": logs,
            "任务包": taskpkg,
            "任务包提示": taskpkg_hint,
            "事实审核": review.get("事实审核"),
            "教学完整性": review.get("教学完整性"),
            "教学问题": review.get("教学问题", []),
            "教学完整率": review.get("教学完整率"),
            "目标考核对齐率": review.get("目标考核对齐率"),
            "关键步骤可判定率": review.get("关键步骤可判定率"),
        }


if __name__ == "__main__":
    result = run("数控机床操作工", question="M代码编程")
    print(result["流程状态"], result["培训内容"].get("标题"))
