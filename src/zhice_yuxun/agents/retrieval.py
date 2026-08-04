"""知识检索 Agent：中文字符向量 + ChromaDB，可溯源且不做无关兜底。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import chromadb

from ..contracts import validate_knowledge_item
from knowledge_base.build_chromadb import (
    COLLECTION_NAME,
    DEFAULT_DATA_PATH,
    DEFAULT_DB_PATH,
    build_database,
)
from knowledge_base.embedding import HashingEmbeddingFunction, normalize_text


# 0.28 可拒绝 E1 发现的跨领域误命中（“核电站操作规程”=0.2686），
# 同时保留当前 QA 初稿中最低的有效预期命中（QA-023=0.2871）。
MIN_RELEVANCE = 0.28
TOP_K = 3
EXPERIMENTAL_ONLY_TERMS = (
    "工业互联网",
    "modbus",
    "opcua",
    "opc-ua",
    "边缘网关",
    "onnx",
    "模型部署",
    "焊接",
)

_SYNONYMS = {
    "安全操作": ["防护门", "急停", "个人防护", "开机检查"],
    "量具": ["卡尺", "千分尺", "测量", "质量检测"],
    "质检": ["质量检测", "量具", "尺寸测量"],
    "加工缺陷": ["振纹", "振动", "故障排除", "碰撞"],
    "缺陷分析": ["振纹", "振动", "故障排除"],
    "M代码": ["M03", "M05", "M08", "M09", "M30", "CNC编程"],
    "维护": ["周期检查", "日常点检", "设备维护"],
}


def _expand_query(question: str) -> str:
    normalized = normalize_text(question)
    additions: list[str] = []
    for trigger, synonyms in _SYNONYMS.items():
        if normalize_text(trigger) in normalized:
            additions.extend(synonyms)
    return question + " " + " ".join(additions)


def _load_items(data_path: Path = DEFAULT_DATA_PATH) -> dict[str, dict[str, Any]]:
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    items: dict[str, dict[str, Any]] = {}
    for item in raw:
        validate_knowledge_item(item)
        if item.get("验证状态") == "已验证":
            items[item["知识ID"]] = item
    return items


def _get_collection(db_path: Path = DEFAULT_DB_PATH):
    items = _load_items()
    client = chromadb.PersistentClient(path=str(db_path))
    try:
        collection = client.get_collection(
            COLLECTION_NAME,
            embedding_function=HashingEmbeddingFunction(),
        )
        if collection.count() != len(items):
            build_database(db_path=db_path)
            collection = client.get_collection(
                COLLECTION_NAME,
                embedding_function=HashingEmbeddingFunction(),
            )
    except Exception:
        build_database(db_path=db_path)
        collection = client.get_collection(
            COLLECTION_NAME,
            embedding_function=HashingEmbeddingFunction(),
        )
    return collection, items


def search_knowledge(question: str) -> list[dict[str, Any]]:
    """返回最多 3 条已验证知识；低相关或未知问题返回空列表。"""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question 必须是非空字符串")
    normalized_question = normalize_text(question)
    if any(
        normalize_text(term) in normalized_question
        for term in EXPERIMENTAL_ONLY_TERMS
    ):
        return []

    collection, items = _get_collection(
        Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_DB_PATH)))
    )
    query = _expand_query(question.strip())
    result = collection.query(
        query_texts=[query],
        n_results=min(TOP_K, max(collection.count(), 1)),
        include=["distances"],
    )
    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]

    output: list[dict[str, Any]] = []
    for knowledge_id, distance in zip(ids, distances):
        score = max(0.0, 1.0 - float(distance))
        if score < MIN_RELEVANCE or knowledge_id not in items:
            continue
        item = items[knowledge_id]
        output.append(
            {
                "知识ID": item["知识ID"],
                "内容": item["内容"],
                "来源": item["来源"],
                "来源定位": item["来源定位"],
                "主题": list(item["主题"]),
                "验证状态": item["验证状态"],
                "检索分数": round(score, 4),
            }
        )
    return output


if __name__ == "__main__":
    for test_question in ["数控机床安全操作", "M代码编程", "量具使用", "量子计算"]:
        print(f"\n问题：{test_question}")
        for item in search_knowledge(test_question):
            print(f"  {item['知识ID']} {item['检索分数']:.2f} {item['内容']}")
