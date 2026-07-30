"""从结构化知识切片构建本地 ChromaDB。

运行前：source venv/bin/activate
运行：python knowledge_base/build_chromadb.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.zhice_yuxun.contracts import validate_knowledge_item
from knowledge_base.embedding import HashingEmbeddingFunction


DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "knowledge.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "manufacturing_knowledge"


def load_verified_knowledge(path: Path = DEFAULT_DATA_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"知识文件不存在：{path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("知识文件顶层必须是列表")
    verified: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in raw:
        validate_knowledge_item(item)
        knowledge_id = item["知识ID"]
        if knowledge_id in seen_ids:
            raise ValueError(f"知识ID重复：{knowledge_id}")
        seen_ids.add(knowledge_id)
        if item.get("验证状态") == "已验证":
            verified.append(item)
    return verified


def build_database(
    data_path: Path = DEFAULT_DATA_PATH,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    items = load_verified_knowledge(data_path)
    if not items:
        raise ValueError("没有“已验证”的知识条目，拒绝建立空知识库")

    client = chromadb.PersistentClient(path=str(db_path))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME,
        embedding_function=HashingEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[item["知识ID"] for item in items],
        documents=[
            item["内容"] + " " + " ".join(item["主题"])
            for item in items
        ],
        metadatas=[
            {
                "来源": item["来源"],
                "来源定位": item["来源定位"],
                "主题": "|".join(item["主题"]),
                "验证状态": item.get("验证状态", ""),
            }
            for item in items
        ],
    )
    return len(items)


if __name__ == "__main__":
    count = build_database()
    print(f"ChromaDB 构建完成：{count} 条已验证知识")
