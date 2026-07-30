"""目录迁移后的规范导入与旧入口兼容回归测试。"""

from pathlib import Path


def test_project_root_is_derived_from_package_location():
    from src.zhice_yuxun.paths import PROJECT_ROOT

    assert PROJECT_ROOT == Path(__file__).resolve().parents[1]
    assert (PROJECT_ROOT / "knowledge_base" / "skill_ontology.json").is_file()


def test_legacy_module_imports_point_to_canonical_implementations():
    import contracts
    import llm_client
    import orchestrator
    import src.zhice_yuxun.contracts as canonical_contracts
    import src.zhice_yuxun.llm_client as canonical_llm_client
    import src.zhice_yuxun.orchestrator as canonical_orchestrator

    assert contracts is canonical_contracts
    assert llm_client is canonical_llm_client
    assert orchestrator is canonical_orchestrator
