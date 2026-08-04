"""证据文件的非覆盖写入与最近版本查找。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_versioned(directory: Path, filename: str, data: Any) -> Path:
    """以独占方式写 JSON；同名文件存在时自动追加 ``_rerun_NN``。"""
    directory.mkdir(parents=True, exist_ok=True)
    requested = Path(filename)
    for number in range(1000):
        suffix = "" if number == 0 else f"_rerun_{number:02d}"
        candidate = directory / f"{requested.stem}{suffix}{requested.suffix}"
        try:
            with candidate.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"无法为证据文件分配新编号：{filename}")


def latest_versioned_file(directory: Path, filename: str) -> Path | None:
    """返回基础文件或其 ``_rerun_NN`` 版本中编号最大的一个。"""
    requested = Path(filename)
    candidates = list(directory.glob(f"{requested.stem}{requested.suffix}"))
    candidates.extend(directory.glob(f"{requested.stem}_rerun_[0-9][0-9]{requested.suffix}"))
    if not candidates:
        return None

    def version(path: Path) -> int:
        if path.stem == requested.stem:
            return 0
        return int(path.stem.rsplit("_rerun_", 1)[1])

    return max(candidates, key=version)
