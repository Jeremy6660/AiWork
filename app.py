"""Streamlit 兼容启动入口。

界面实现位于 ``src/zhice_yuxun/ui.py``；保留本文件以兼容
``streamlit run app.py``。Streamlit 会重复执行入口脚本，因此这里不能使用
会命中模块缓存的普通导入。
"""

from runpy import run_module


run_module("src.zhice_yuxun.ui", run_name="__main__")
