"""旧导入兼容层；规范实现位于 ``src.zhice_yuxun.contracts``。"""

import sys

from src.zhice_yuxun import contracts as _implementation


sys.modules[__name__] = _implementation
