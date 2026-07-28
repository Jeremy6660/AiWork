import csv
import json

import pytest

from knowledge_base.export_review_csv import (
    REVIEW_FIELDS,
    export_review_csv,
    validate_cases,
)


def _knowledge(knowledge_id: str = "K-001") -> dict:
    return {
        "知识ID": knowledge_id,
        "内容": "机床运行前应完成安全检查。",
        "来源": "设备官方手册",
        "来源定位": "https://example.com/manual#safety",
        "主题": ["安全操作"],
        "验证状态": "已验证",
    }


def _case(case_id: str = "QA-001", *, status: str = "机器初标，待人工双人复核"):
    return {
        "案例ID": case_id,
        "问题": "机床运行前应做什么？",
        "岗位": "数控机床操作工",
        "画像组": "P1",
        "目标难度": "入门",
        "预期知识ID": ["K-001"],
        "参考答案": "应完成安全检查。",
        "依据来源": "设备官方手册",
        "来源定位": "https://example.com/manual#safety",
        "标注状态": status,
    }


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_duplicate_case_ids_are_rejected():
    with pytest.raises(ValueError, match="案例ID重复"):
        validate_cases([_case(), _case()], [_knowledge()])


def test_missing_case_source_location_is_rejected():
    case = _case()
    case["来源定位"] = ""

    with pytest.raises(ValueError, match="缺少来源定位"):
        validate_cases([case], [_knowledge()])


def test_illegal_label_status_is_rejected():
    with pytest.raises(ValueError, match="非法标注状态"):
        validate_cases([_case(status="AI已自动审核通过")], [_knowledge()])


def test_export_keeps_all_human_review_fields_blank(tmp_path):
    cases_path = _write_json(tmp_path / "cases.json", [_case()])
    knowledge_path = _write_json(tmp_path / "knowledge.json", [_knowledge()])
    output_path = tmp_path / "review.csv"

    count = export_review_csv(cases_path, knowledge_path, output_path)

    assert count == 1
    assert output_path.read_bytes().startswith(b"\xef\xbb\xbf")
    with output_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["案例ID"] == "QA-001"
    assert rows[0]["预期知识ID"] == "K-001"
    assert all(rows[0][field] == "" for field in REVIEW_FIELDS)


def test_current_52_case_dataset_passes_structure_validation():
    from knowledge_base.export_review_csv import (
        DEFAULT_CASES_PATH,
        DEFAULT_KNOWLEDGE_PATH,
        load_json_list,
    )

    cases = load_json_list(DEFAULT_CASES_PATH, "评测集")
    knowledge = load_json_list(DEFAULT_KNOWLEDGE_PATH, "知识库")

    validate_cases(cases, knowledge)

    assert len(cases) == 52
