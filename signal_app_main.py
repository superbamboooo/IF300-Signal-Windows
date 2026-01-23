#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
多策略交易信号系统 - 主程序
================================================================================
支持策略：
1. IF300 V10.14 - 股指期货季月合约策略
2. 周末效应 V9 - 创业板ETF周末效应策略
================================================================================
"""

import tkinter as tk
from tkinter import ttk
import warnings
warnings.filterwarnings('ignore')

# 导入两个策略的界面模块
from strategy_if300 import IF300StrategyFrame
from strategy_weekend import WeekendStrategyFrame


class MultiStrategyApp:
    """多策略交易信号系统主程序"""

    def __init__(self, root):
        self.root = root
        self.root.title("多策略交易信号系统")
        self.root.geometry("1100x900")
        self.root.minsize(1000, 800)

        # 创建主框架
        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        # 创建Notebook（标签页容器）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建两个策略的Frame
        self.if300_frame = ttk.Frame(self.notebook)
        self.weekend_frame = ttk.Frame(self.notebook)

        # 添加标签页
        self.notebook.add(self.if300_frame, text="  IF300 股指期货策略  ")
        self.notebook.add(self.weekend_frame, text="  周末效应 创业板ETF策略  ")

        # 初始化两个策略界面（完全独立）
        self.if300_strategy = IF300StrategyFrame(self.if300_frame)
        self.weekend_strategy = WeekendStrategyFrame(self.weekend_frame)

        # 绑定标签切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        """标签页切换事件"""
        # 可以在这里处理标签切换时的逻辑
        pass


def main():
    root = tk.Tk()
    app = MultiStrategyApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
