"""项目内稳定路径定义。

运行代码集中在 ``src/zhice_yuxun`` 后，所有资源路径都从仓库根目录推导，
避免依赖当前工作目录。
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
