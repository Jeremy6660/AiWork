"""旧导入兼容层；规范实现位于 ``src.zhice_yuxun.orchestrator``。"""

import sys

from src.zhice_yuxun import orchestrator as _implementation


sys.modules[__name__] = _implementation
