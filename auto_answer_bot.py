# -*- coding: utf-8 -*-
"""
全自动答题机器人 v4.0 — 入口文件
==================================
保持对 bat 脚本的兼容，实际逻辑在 main.py
"""

import sys

# 控制台编码修正
if sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'gb18030'):
    sys.stdout.reconfigure(encoding='utf-8')

from main import main

if __name__ == "__main__":
    main()