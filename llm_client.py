"""旧导入兼容层；规范实现位于 ``src.zhice_yuxun.llm_client``。"""

import sys

from src.zhice_yuxun import llm_client as _implementation


sys.modules[__name__] = _implementation
