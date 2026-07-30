import json
from pathlib import Path

import pytest

from src.zhice_yuxun.contracts import ContractError
from knowledge_base.build_chromadb import load_verified_knowledge


def _knowledge(knowledge_id: str, *, status: str = "已验证") -> dict:
    return {
        "知识ID": knowledge_id,
        "内容": "机床运行前应完成安全检查。",
        "来源": "设备官方手册",
        "来源定位": "https://example.com/manual#safety",
        "主题": ["安全操作"],
        "验证状态": status,
    }


def _write_knowledge(tmp_path, items: list[dict]):
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def test_duplicate_knowledge_ids_are_rejected(tmp_path):
    path = _write_knowledge(tmp_path, [_knowledge("K-001"), _knowledge("K-001")])

    with pytest.raises(ValueError, match="知识ID重复"):
        load_verified_knowledge(path)


def test_missing_source_location_is_rejected(tmp_path):
    item = _knowledge("K-001")
    item.pop("来源定位")
    path = _write_knowledge(tmp_path, [item])

    with pytest.raises(ContractError, match="来源定位"):
        load_verified_knowledge(path)


def test_unverified_knowledge_is_not_loaded(tmp_path):
    path = _write_knowledge(
        tmp_path,
        [_knowledge("K-001"), _knowledge("K-002", status="待人工核验")],
    )

    loaded = load_verified_knowledge(path)

    assert [item["知识ID"] for item in loaded] == ["K-001"]


def test_current_corpus_is_traceable_and_unique():
    loaded = load_verified_knowledge()
    ids = [item["知识ID"] for item in loaded]

    assert loaded
    assert len(ids) == len(set(ids))
    assert len(loaded) == 39
    assert all(item["来源定位"].strip() for item in loaded)
    assert all(item["验证状态"] == "已验证" for item in loaded)


def test_current_corpus_keeps_nine_drafts_out_of_verified_index():
    path = Path(__file__).resolve().parents[1] / "data" / "knowledge.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    drafts = [item for item in raw if item.get("验证状态") == "待人工核验"]

    assert len(raw) == 48
    assert len(drafts) == 9
    assert {item["知识ID"] for item in drafts} == {
        "IIOT-PROTO-001",
        "IIOT-PROTO-002",
        "IIOT-EDGE-001",
        "IIOT-PLC-001",
        "AI-DEPLOY-001",
        "AI-ANNOTATE-001",
        "AI-ML-OPS-001",
        "IIOT-SECURITY-001",
        "PYTHON-DATA-001",
    }
