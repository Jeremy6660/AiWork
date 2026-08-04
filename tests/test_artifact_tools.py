import json

from scripts.artifact_io import latest_versioned_file, write_json_versioned
from scripts.verify_artifact_hashes import DEFAULT_MANIFEST, verify_manifest


def test_p2_canonical_hash_manifest_verifies_across_line_endings():
    assert verify_manifest(DEFAULT_MANIFEST) == []


def test_versioned_json_write_never_overwrites_existing_evidence(tmp_path):
    original = write_json_versioned(tmp_path, "evidence.json", {"run": 1})
    rerun = write_json_versioned(tmp_path, "evidence.json", {"run": 2})

    assert original.name == "evidence.json"
    assert rerun.name == "evidence_rerun_01.json"
    assert json.loads(original.read_text(encoding="utf-8")) == {"run": 1}
    assert json.loads(rerun.read_text(encoding="utf-8")) == {"run": 2}
    assert latest_versioned_file(tmp_path, "evidence.json") == rerun
