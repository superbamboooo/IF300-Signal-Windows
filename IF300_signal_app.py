#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 V10.14 交易信号系统 - Windows桌面应用程序
================================================================================
功能：
1. 自动加载和显示K线数据
2. 自动计算MA60均线
3. 实时判断交易信号（做多/做空）
4. 显示当前持仓状态和止损/平仓提示
5. 支持数据更新
================================================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import threading
import warnings
warnings.filterwarnings('ignore')

# matplotlib 用于绘制K线图
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates

# 设置中文字体
import platform
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
elif platform.system() == 'Windows':
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
else:  # Linux
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# ==================== 策略参数（与V10.14一致）====================
# 做多参数
LONG_WEEKDAYS = [2, 3]  # 周三、周四
LONG_MA_MIN = 0.99
LONG_MA_MAX = 1.10
LONG_EXCLUDE_MONTHS = []
LONG_HOLD_DAYS = 3
LONG_STOP_LOSS = 0.02

# 做空参数A（排除12月）
SHORT_A_WEEKDAYS = [0]  # 周一
SHORT_A_MA_MIN = 0.98
SHORT_A_MA_MAX = 1.10
SHORT_A_EXCLUDE_MONTHS = [12]
SHORT_A_HOLD_DAYS = 4
SHORT_A_STOP_LOSS = 0.015

# 做空参数B（仅12月）
SHORT_B_WEEKDAYS = [4]  # 周五
SHORT_B_MA_MAX = 1.00
SHORT_B_ONLY_MONTHS = [12]
SHORT_B_HOLD_DAYS = 5
SHORT_B_STOP_LOSS = 0.02

WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def get_data_path():
    """获取数据目录路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的路径
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境路径
        base_path = os.path.dirname(os.path.abspath(__file__))

    # 数据在上级目录的data文件夹
    data_path = os.path.join(os.path.dirname(base_path), 'data')
    if not os.path.exists(data_path):
        data_path = os.path.join(base_path, 'data')
    return data_path


def get_delivery_dates(start_year=2015, end_year=2030):
    """生成季月合约交割日列表（3/6/9/12月的第三个周五）"""
    delivery_dates = []
    quarterly_months = [3, 6, 9, 12]  # 季月
    for year in range(start_year, end_year + 1):
        for month in quarterly_months:
            first_day = datetime(year, month, 1)
            weekday = first_day.weekday()
            if weekday <= 4:
                first_friday = first_day + timedelta(days=(4 - weekday))
            else:
                first_friday = first_day + timedelta(days=(11 - weekday))
            third_friday = first_friday + timedelta(days=14)
            delivery_dates.append(pd.Timestamp(third_friday))
    return delivery_dates


def get_delivery_week_dates(delivery_dates):
    """生成所有交割周日期（周一到周五）的集合"""
    delivery_week_set = set()
    for dd in delivery_dates:
        monday = dd - timedelta(days=4)
        for i in range(5):
            day = monday + timedelta(days=i)
            delivery_week_set.add(day)
    return delivery_week_set


class IF300SignalApp:
    """IF300交易信号桌面应用"""

    def __init__(self, root):
        self.root = root
        self.root.title("IF300 V10.14 交易信号系统")
        self.root.geometry("1000x800")
        self.root.minsize(900, 700)

        # 数据变量
        self.df = None
        self.delivery_dates = get_delivery_dates()
        self.delivery_week_set = get_delivery_week_dates(self.delivery_dates)

        # 创建界面
        self.create_widgets()

        # 自动加载数据
        self.root.after(100, self.load_data)

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 顶部信息区 =====
        top_frame = ttk.LabelFrame(main_frame, text="当前市场状态", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # 第一行：日期和价格
        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="日期:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.date_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.date_var, font=('微软雅黑', 22, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row1, text="星期:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.weekday_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.weekday_var, font=('微软雅黑', 22, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row1, text="收盘价:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.price_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.price_var, font=('微软雅黑', 22, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=(5, 30))

        # 右侧按钮
        ttk.Button(row1, text="更新数据", command=self.update_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(row1, text="刷新", command=self.load_data).pack(side=tk.RIGHT, padx=5)

        # 第二行：MA60和比率
        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="MA60:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.ma60_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ma60_var, font=('微软雅黑', 22, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row2, text="价格/MA60:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.ratio_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ratio_var, font=('微软雅黑', 22, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row2, text="交割周:", font=('微软雅黑', 18)).pack(side=tk.LEFT)
        self.delivery_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.delivery_var, font=('微软雅黑', 22, 'bold')).pack(side=tk.LEFT, padx=(5, 0))

        # ===== 信号显示区 =====
        signal_frame = ttk.LabelFrame(main_frame, text="交易信号条件", padding="10")
        signal_frame.pack(fill=tk.X, pady=(0, 10))

        # 左右两列布局
        signal_cols = ttk.Frame(signal_frame)
        signal_cols.pack(fill=tk.X)

        # 左列：做多条件
        self.long_frame = ttk.LabelFrame(signal_cols, text="做多条件", padding="5")
        self.long_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.long_weekday_var = tk.StringVar(value="星期: --")
        self.long_weekday_label = ttk.Label(self.long_frame, textvariable=self.long_weekday_var, font=('微软雅黑', 18))
        self.long_weekday_label.pack(anchor=tk.W)

        self.long_ma_var = tk.StringVar(value="MA比率: --")
        self.long_ma_label = ttk.Label(self.long_frame, textvariable=self.long_ma_var, font=('微软雅黑', 18))
        self.long_ma_label.pack(anchor=tk.W)

        self.long_delivery_var = tk.StringVar(value="交割周: --")
        self.long_delivery_label = ttk.Label(self.long_frame, textvariable=self.long_delivery_var, font=('微软雅黑', 18))
        self.long_delivery_label.pack(anchor=tk.W)

        self.long_stoploss_var = tk.StringVar(value="")
        self.long_stoploss_label = ttk.Label(self.long_frame, textvariable=self.long_stoploss_var, font=('微软雅黑', 18, 'bold'), foreground='red')
        self.long_stoploss_label.pack(anchor=tk.W, pady=(5, 0))

        # 右列：做空条件
        self.short_frame = ttk.LabelFrame(signal_cols, text="做空条件", padding="5")
        self.short_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.short_weekday_var = tk.StringVar(value="星期: --")
        self.short_weekday_label = ttk.Label(self.short_frame, textvariable=self.short_weekday_var, font=('微软雅黑', 18))
        self.short_weekday_label.pack(anchor=tk.W)

        self.short_month_var = tk.StringVar(value="月份: --")
        self.short_month_label = ttk.Label(self.short_frame, textvariable=self.short_month_var, font=('微软雅黑', 18))
        self.short_month_label.pack(anchor=tk.W)

        self.short_ma_var = tk.StringVar(value="MA比率: --")
        self.short_ma_label = ttk.Label(self.short_frame, textvariable=self.short_ma_var, font=('微软雅黑', 18))
        self.short_ma_label.pack(anchor=tk.W)

        self.short_stoploss_var = tk.StringVar(value="")
        self.short_stoploss_label = ttk.Label(self.short_frame, textvariable=self.short_stoploss_var, font=('微软雅黑', 18, 'bold'), foreground='green')
        self.short_stoploss_label.pack(anchor=tk.W, pady=(5, 0))

        # ===== 可开仓价格区间 =====
        price_range_frame = ttk.LabelFrame(main_frame, text="可开仓价格区间（基于MA60条件）", padding="10")
        price_range_frame.pack(fill=tk.X, pady=(0, 10))

        price_range_cols = ttk.Frame(price_range_frame)
        price_range_cols.pack(fill=tk.X)

        # 左列：做多价格区间
        long_range_frame = ttk.Frame(price_range_cols)
        long_range_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(long_range_frame, text="做多:", font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT)
        self.long_price_range_var = tk.StringVar(value="-- ~ --")
        ttk.Label(long_range_frame, textvariable=self.long_price_range_var, font=('微软雅黑', 22, 'bold'), foreground='#006400').pack(side=tk.LEFT, padx=(5, 0))

        # 右列：做空价格区间
        short_range_frame = ttk.Frame(price_range_cols)
        short_range_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        ttk.Label(short_range_frame, text="做空:", font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT)
        self.short_price_range_var = tk.StringVar(value="-- ~ --")
        ttk.Label(short_range_frame, textvariable=self.short_price_range_var, font=('微软雅黑', 22, 'bold'), foreground='#8B0000').pack(side=tk.LEFT, padx=(5, 0))

        # ===== K线图区 =====
        chart_frame = ttk.LabelFrame(main_frame, text="K线图", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建 matplotlib 图形（增大高度）
        self.fig, self.ax = plt.subplots(figsize=(10, 5), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax.set_facecolor('#ffffff')

        # 嵌入到 tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # K线数据提示（鼠标悬停显示）
        self.kline_data = None  # 存储当前绘图的K线数据
        self.hover_annotation = None  # 悬停提示框
        self.hover_vline = None  # 垂直指示线
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # ===== 底部按钮区 =====
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X)

        ttk.Button(bottom_frame, text="策略说明", command=self.show_strategy_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="退出", command=self.root.quit).pack(side=tk.RIGHT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))

    def load_data(self):
        """加载数据"""
        self.status_var.set("正在加载数据...")
        self.root.update()

        try:
            data_path = get_data_path()

            # 加载IF季月合约数据
            if_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')
            if not os.path.exists(if_path):
                messagebox.showerror("错误", f"找不到数据文件:\n{if_path}")
                self.status_var.set("数据加载失败")
                return

            df_if = pd.read_csv(if_path)
            df_if['日期'] = pd.to_datetime(df_if['日期'])
            df_if = df_if.sort_values('日期').reset_index(drop=True)

            # 标准化列名：处理可能存在的多套价格列
            for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
                if old_col in df_if.columns and new_col in df_if.columns:
                    mask = df_if[new_col].isna()
                    if mask.any():
                        df_if.loc[mask, new_col] = df_if.loc[mask, old_col]

            # 确保有合约列，并填充空值
            if '合约' not in df_if.columns:
                df_if['合约'] = ''

            # 根据日期推断季月合约代码（填充空值）
            def infer_quarterly_contract(date):
                year = date.year
                month = date.month
                quarterly_months = [3, 6, 9, 12]
                for qm in quarterly_months:
                    if qm >= month:
                        # 计算该季月的交割日
                        first_day = datetime(year, qm, 1)
                        wd = first_day.weekday()
                        if wd <= 4:
                            first_fri = first_day + timedelta(days=(4 - wd))
                        else:
                            first_fri = first_day + timedelta(days=(11 - wd))
                        third_fri = first_fri + timedelta(days=14)
                        if date.date() <= third_fri.date():
                            return f"IF{year % 100:02d}{qm:02d}"
                # 下一年3月
                return f"IF{(year + 1) % 100:02d}03"

            # 填充空的合约列
            mask = df_if['合约'].isna() | (df_if['合约'] == '')
            if mask.any():
                df_if.loc[mask, '合约'] = df_if.loc[mask, '日期'].apply(infer_quarterly_contract)

            # 加载沪深300指数数据（用于预热MA60）
            idx_path = os.path.join(data_path, '000300_沪深300_day.csv')
            if os.path.exists(idx_path):
                df_idx = pd.read_csv(idx_path)
                df_idx['日期'] = pd.to_datetime(df_idx['日期'])
                df_idx = df_idx.sort_values('日期').reset_index(drop=True)

                if_start_date = df_if['日期'].min()
                warmup_days = 120
                df_idx_warmup = df_idx[df_idx['日期'] < if_start_date].tail(warmup_days).copy()

                first_if_close = df_if.iloc[0]['收盘']
                idx_on_if_start = df_idx[df_idx['日期'] == if_start_date]
                price_ratio = first_if_close / idx_on_if_start.iloc[0]['收盘'] if len(idx_on_if_start) > 0 else 1.0

                for col in ['收盘', '开盘', '最高', '最低']:
                    df_idx_warmup[col] = df_idx_warmup[col] * price_ratio

                df_idx_warmup['is_warmup'] = True
                df_idx_warmup['合约'] = ''
                df_if['is_warmup'] = False

                self.df = pd.concat([df_idx_warmup[['日期', '开盘', '最高', '最低', '收盘', '合约', 'is_warmup']],
                                     df_if[['日期', '开盘', '最高', '最低', '收盘', '合约', 'is_warmup']]], ignore_index=True)
            else:
                df_if['is_warmup'] = False
                self.df = df_if[['日期', '开盘', '最高', '最低', '收盘', '合约', 'is_warmup']].copy()

            self.df = self.df.sort_values('日期').reset_index(drop=True)
            self.df['weekday'] = self.df['日期'].dt.weekday
            self.df['month'] = self.df['日期'].dt.month
            self.df['MA60'] = self.df['收盘'].rolling(60).mean()

            # 更新界面
            self.update_display()

            data_start = self.df[self.df['is_warmup'] == False]['日期'].min().strftime('%Y-%m-%d')
            data_end = self.df['日期'].max().strftime('%Y-%m-%d')
            self.status_var.set(f"数据加载完成 | 数据范围: {data_start} ~ {data_end}")

        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败:\n{str(e)}")
            self.status_var.set("数据加载失败")

    def update_display(self):
        """更新界面显示"""
        if self.df is None or len(self.df) == 0:
            return

        # 获取最新数据
        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        current_date = latest['日期']
        price = latest['收盘']
        ma60 = latest['MA60']
        weekday = latest['weekday']
        month = latest['month']

        # 更新顶部信息
        self.date_var.set(current_date.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.2f}")
        self.ma60_var.set(f"{ma60:.2f}" if not pd.isna(ma60) else "--")

        if not pd.isna(ma60):
            ratio = price / ma60
            self.ratio_var.set(f"{ratio:.4f} ({ratio*100:.2f}%)")
        else:
            ratio = None
            self.ratio_var.set("--")

        # 检查是否交割周
        is_delivery_week = current_date in self.delivery_week_set
        self.delivery_var.set("是" if is_delivery_week else "否")

        # 分析交易信号
        self.analyze_signal(current_date, price, ma60, weekday, month, is_delivery_week)

        # 计算可开仓价格区间
        self.update_price_range(month)

        # 更新K线图
        self.update_kline_chart()

    def analyze_signal(self, current_date, price, ma60, weekday, month, is_delivery_week):
        """分析交易信号"""
        if pd.isna(ma60):
            self.long_weekday_var.set("MA60数据不足")
            self.long_ma_var.set("")
            self.long_delivery_var.set("")
            self.long_stoploss_var.set("")
            self.long_frame.configure(text="做多条件")
            self.short_weekday_var.set("MA60数据不足")
            self.short_month_var.set("")
            self.short_ma_var.set("")
            self.short_stoploss_var.set("")
            self.short_frame.configure(text="做空条件")
            return

        ratio = price / ma60

        # ===== 做多条件分析 =====
        # 条件1：星期（周三或周四）
        long_weekday_ok = weekday in LONG_WEEKDAYS
        weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (需要周三/周四)"
        self.long_weekday_var.set(weekday_text)
        self.long_weekday_label.configure(foreground='green' if long_weekday_ok else 'red')

        # 条件2：MA比率（99%~110%）
        long_ma_ok = LONG_MA_MIN <= ratio <= LONG_MA_MAX
        ma_text = f"MA比率: {ratio:.2%} (需要{LONG_MA_MIN:.0%}~{LONG_MA_MAX:.0%})"
        self.long_ma_var.set(ma_text)
        self.long_ma_label.configure(foreground='green' if long_ma_ok else 'red')

        # 条件3：非交割周周四
        long_delivery_ok = not (is_delivery_week and weekday == 3)
        if is_delivery_week:
            delivery_text = f"交割周: 是 (周四不开仓)"
        else:
            delivery_text = f"交割周: 否"
        self.long_delivery_var.set(delivery_text)
        self.long_delivery_label.configure(foreground='green' if long_delivery_ok else 'red')

        # 做多结果 - 更新标题和止损价
        long_signal = long_weekday_ok and long_ma_ok and long_delivery_ok
        if long_signal:
            self.long_frame.configure(text="做多条件（满足）")
            self.long_stoploss_var.set(f"止损价: {price*(1-LONG_STOP_LOSS):.0f}")
        else:
            self.long_frame.configure(text="做多条件（不满足）")
            self.long_stoploss_var.set("")

        # ===== 做空条件分析 =====
        # 判断使用哪套做空策略
        if month == 12:
            # 12月使用策略B
            short_weekday_ok = weekday in SHORT_B_WEEKDAYS
            weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (12月需要周五)"
            self.short_weekday_var.set(weekday_text)
            self.short_weekday_label.configure(foreground='green' if short_weekday_ok else 'red')

            self.short_month_var.set(f"月份: {month}月 (12月策略B)")
            self.short_month_label.configure(foreground='green')

            short_ma_ok = ratio <= SHORT_B_MA_MAX
            ma_text = f"MA比率: {ratio:.2%} (需要≤{SHORT_B_MA_MAX:.0%})"
            self.short_ma_var.set(ma_text)
            self.short_ma_label.configure(foreground='green' if short_ma_ok else 'red')

            short_signal = short_weekday_ok and short_ma_ok
            stop_loss = SHORT_B_STOP_LOSS
        else:
            # 非12月使用策略A
            short_weekday_ok = weekday in SHORT_A_WEEKDAYS
            weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (非12月需要周一)"
            self.short_weekday_var.set(weekday_text)
            self.short_weekday_label.configure(foreground='green' if short_weekday_ok else 'red')

            self.short_month_var.set(f"月份: {month}月 (非12月策略A)")
            self.short_month_label.configure(foreground='green')

            short_ma_ok = SHORT_A_MA_MIN <= ratio <= SHORT_A_MA_MAX
            ma_text = f"MA比率: {ratio:.2%} (需要{SHORT_A_MA_MIN:.0%}~{SHORT_A_MA_MAX:.0%})"
            self.short_ma_var.set(ma_text)
            self.short_ma_label.configure(foreground='green' if short_ma_ok else 'red')

            short_signal = short_weekday_ok and short_ma_ok
            stop_loss = SHORT_A_STOP_LOSS

        # 做空结果 - 更新标题和止损价
        if short_signal:
            self.short_frame.configure(text="做空条件（满足）")
            self.short_stoploss_var.set(f"止损价: {price*(1+stop_loss):.0f}")
        else:
            self.short_frame.configure(text="做空条件（不满足）")
            self.short_stoploss_var.set("")

    def update_price_range(self, month):
        """计算并更新可开仓价格区间

        公式推导：
        设 S59 = 最近59天收盘价之和（不含目标日）
        目标日收盘价为 P，则 MA60 = (S59 + P) / 60
        比率 ratio = P / MA60 = 60P / (S59 + P)

        解不等式 ratio_min ≤ 60P/(S59+P) ≤ ratio_max：
        P_min = ratio_min × S59 / (60 - ratio_min)
        P_max = ratio_max × S59 / (60 - ratio_max)
        """
        if self.df is None or len(self.df) == 0:
            self.long_price_range_var.set("-- ~ --")
            self.short_price_range_var.set("-- ~ --")
            return

        # 获取有效数据（非warmup）
        valid_df = self.df[self.df['is_warmup'] == False]
        if len(valid_df) < 60:
            self.long_price_range_var.set("数据不足60天")
            self.short_price_range_var.set("数据不足60天")
            return

        # S59 = 最近59天收盘价之和（不含最后一天，因为最后一天是"当前/目标日"）
        # 如果要预测"明天"的区间，S59 = 最近59天（包括今天）
        # 这里我们计算的是：如果今天收盘价为P，MA60条件是否满足
        # 所以 S59 = 最近59天（不含今天）的收盘价之和
        recent_60 = valid_df.tail(60)['收盘'].values
        S59 = recent_60[:-1].sum()  # 不含最后一天

        # 计算做多价格区间
        long_p_min = LONG_MA_MIN * S59 / (60 - LONG_MA_MIN)
        long_p_max = LONG_MA_MAX * S59 / (60 - LONG_MA_MAX)
        self.long_price_range_var.set(f"{long_p_min:.0f} ~ {long_p_max:.0f}")

        # 计算做空价格区间（根据月份选择策略）
        if month == 12:
            # 12月策略B：ratio ≤ 100%
            short_p_max = SHORT_B_MA_MAX * S59 / (60 - SHORT_B_MA_MAX)
            self.short_price_range_var.set(f"≤ {short_p_max:.0f}")
        else:
            # 非12月策略A：98% ~ 110%
            short_p_min = SHORT_A_MA_MIN * S59 / (60 - SHORT_A_MA_MIN)
            short_p_max = SHORT_A_MA_MAX * S59 / (60 - SHORT_A_MA_MAX)
            self.short_price_range_var.set(f"{short_p_min:.0f} ~ {short_p_max:.0f}")

    def update_kline_chart(self):
        """更新K线图"""
        if self.df is None:
            return

        # 清空图形
        self.ax.clear()

        # 重置悬停对象（因为ax.clear()会清除它们）
        self.hover_annotation = None
        self.hover_vline = None

        # 获取最近60条数据用于绘图
        recent_data = self.df[self.df['is_warmup'] == False].tail(60).copy()
        recent_data = recent_data.reset_index(drop=True)

        if len(recent_data) == 0:
            return

        # 获取价格范围用于绘制标记
        price_min = recent_data['最低'].min()
        price_max = recent_data['最高'].max()
        price_range = price_max - price_min

        # 绘制K线
        width = 0.6

        for i, row in recent_data.iterrows():
            open_price = row['开盘']
            close_price = row['收盘']
            high_price = row['最高']
            low_price = row['最低']

            # 确定颜色：涨红跌绿
            if close_price >= open_price:
                color = 'red'
                body_bottom = open_price
                body_height = close_price - open_price
            else:
                color = 'green'
                body_bottom = close_price
                body_height = open_price - close_price

            # 绘制影线（上下影线）
            self.ax.plot([i, i], [low_price, high_price], color=color, linewidth=1)

            # 绘制实体
            rect = Rectangle((i - width/2, body_bottom), width, body_height if body_height > 0 else 0.1,
                            facecolor=color, edgecolor=color, linewidth=1)
            self.ax.add_patch(rect)

        # 绘制MA60均线
        ma60_data = recent_data['MA60'].dropna()
        if len(ma60_data) > 0:
            ma60_indices = recent_data.loc[ma60_data.index].index.tolist()
            self.ax.plot(ma60_indices, ma60_data.values, color='blue', linewidth=1.5, label='MA60')

        # 绘制合约分割线和标注合约名称
        contracts = recent_data['合约'].tolist()

        # 找出每个合约的起止位置
        contract_ranges = []  # [(start_idx, end_idx, contract_name), ...]
        current_contract = contracts[0] if contracts else ''
        start_idx = 0

        for i, contract in enumerate(contracts):
            if contract != current_contract and contract != '':
                if current_contract:
                    contract_ranges.append((start_idx, i - 1, current_contract))
                start_idx = i
                current_contract = contract

        # 添加最后一个合约区间
        if current_contract:
            contract_ranges.append((start_idx, len(contracts) - 1, current_contract))

        # 标注合约名称（在合约区间中间位置）
        for start, end, contract in contract_ranges:
            mid_pos = (start + end) / 2
            self.ax.text(mid_pos, price_max + price_range * 0.02, contract,
                        fontsize=16, color='purple', ha='center', va='bottom', fontweight='bold')

        # 绘制交割周虚线框
        for i, row in recent_data.iterrows():
            date = row['日期']
            if date in self.delivery_week_set:
                # 交割周用浅灰色背景标记
                rect = Rectangle((i - 0.5, price_min - price_range * 0.02),
                                1, price_range * 1.04,
                                facecolor='yellow', alpha=0.15, edgecolor='orange',
                                linestyle='--', linewidth=0.5)
                self.ax.add_patch(rect)

        # 在K线下方显示星期几
        weekday_chars = ['一', '二', '三', '四', '五', '六', '日']
        for i, row in recent_data.iterrows():
            wd = row['weekday']
            self.ax.text(i, price_min - price_range * 0.03, weekday_chars[wd],
                        fontsize=12, color='gray', ha='center', va='top')

        # 设置X轴标签（每10根显示一个日期）
        step = max(1, len(recent_data) // 6)
        tick_positions = list(range(0, len(recent_data), step))
        tick_labels = [recent_data.iloc[i]['日期'].strftime('%m-%d') for i in tick_positions]
        self.ax.set_xticks(tick_positions)
        self.ax.set_xticklabels(tick_labels, fontsize=14)

        # 设置Y轴
        self.ax.set_ylabel('价格', fontsize=16)
        self.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0f}'))

        # 添加网格
        self.ax.grid(True, alpha=0.3)

        # 添加图例
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='blue', linewidth=1.5, label='MA60'),
            Patch(facecolor='yellow', alpha=0.3, edgecolor='orange', linestyle='--', label='交割周')
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=14)

        # 设置标题（显示当前合约）
        latest_date = recent_data.iloc[-1]['日期'].strftime('%Y-%m-%d')
        latest_contract = recent_data.iloc[-1]['合约'] if recent_data.iloc[-1]['合约'] else '未知'
        self.ax.set_title(f'IF300 季月合约K线图 [{latest_contract}] (截至 {latest_date})', fontsize=18)

        # 调整Y轴范围给合约标注和星期留空间
        self.ax.set_ylim(price_min - price_range * 0.08, price_max + price_range * 0.1)

        # 调整边距
        self.fig.tight_layout()

        # 保存K线数据供鼠标悬停使用
        self.kline_data = recent_data

        # 刷新画布
        self.canvas.draw()

    def on_mouse_move(self, event):
        """鼠标移动事件处理 - 显示K线数据"""
        # 检查是否在坐标轴内
        if event.inaxes != self.ax or self.kline_data is None:
            # 移除悬停提示
            if self.hover_annotation is not None:
                self.hover_annotation.set_visible(False)
            if self.hover_vline is not None:
                self.hover_vline.set_visible(False)
            self.canvas.draw_idle()
            return

        # 获取鼠标x坐标对应的K线索引
        x = event.xdata
        if x is None:
            return

        idx = int(round(x))
        if idx < 0 or idx >= len(self.kline_data):
            return

        # 获取该K线数据
        row = self.kline_data.iloc[idx]
        date = row['日期']
        open_p = row['开盘']
        high_p = row['最高']
        low_p = row['最低']
        close_p = row['收盘']
        contract = row.get('合约', '')

        # 计算涨跌
        if idx > 0:
            prev_close = self.kline_data.iloc[idx-1]['收盘']
            change = close_p - prev_close
            change_pct = change / prev_close * 100
            change_str = f"{change:+.2f} ({change_pct:+.2f}%)"
        else:
            change_str = "--"

        # 构建提示文本
        weekday = WEEKDAY_NAMES[date.weekday()]
        text = (f"{date.strftime('%Y-%m-%d')} {weekday}\n"
                f"合约: {contract}\n"
                f"开: {open_p:.2f}  高: {high_p:.2f}\n"
                f"低: {low_p:.2f}  收: {close_p:.2f}\n"
                f"涨跌: {change_str}")

        # 创建或更新annotation（使用系统已配置的中文字体）
        if self.hover_annotation is None:
            self.hover_annotation = self.ax.annotate(
                text, xy=(idx, high_p), xytext=(10, 10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', edgecolor='gray', alpha=0.95),
                fontsize=16
            )
        else:
            self.hover_annotation.set_text(text)
            self.hover_annotation.xy = (idx, high_p)
            self.hover_annotation.set_visible(True)

        # 创建或更新垂直指示线
        if self.hover_vline is None:
            self.hover_vline = self.ax.axvline(x=idx, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
        else:
            self.hover_vline.set_xdata([idx, idx])
            self.hover_vline.set_visible(True)

        self.canvas.draw_idle()

    def update_data(self):
        """更新K线数据"""
        try:
            # 尝试导入数据更新模块
            from data_updater import update_if_data

            self.status_var.set("正在更新数据...")
            self.root.update()

            def do_update():
                try:
                    result = update_if_data()
                    self.root.after(0, lambda: self.on_update_complete(result))
                except Exception as e:
                    self.root.after(0, lambda: self.on_update_error(str(e)))

            thread = threading.Thread(target=do_update)
            thread.start()

        except ImportError:
            messagebox.showinfo("提示",
                "数据更新模块未安装。\n\n"
                "请手动更新数据文件:\n"
                "1. 从数据源下载最新的IF主连数据\n"
                "2. 保存到 data/IF_主连_季月合约连接_day.csv\n\n"
                "然后点击'刷新数据'按钮重新加载。")

    def on_update_complete(self, result):
        """数据更新完成回调"""
        self.load_data()
        messagebox.showinfo("完成", f"数据更新完成\n{result}")

    def on_update_error(self, error):
        """数据更新错误回调"""
        self.status_var.set("数据更新失败")
        messagebox.showerror("错误", f"数据更新失败:\n{error}")

    def show_strategy_info(self):
        """显示策略说明"""
        info_window = tk.Toplevel(self.root)
        info_window.title("IF300 V10.14 策略说明")
        info_window.geometry("700x600")

        text = scrolledtext.ScrolledText(info_window, font=('微软雅黑', 18), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        strategy_text = """
================================================================================
IF300 V10.14 - 综合最优版本（宽止损）
================================================================================

【版本说明】
基于500K+大规模参数搜索发现的 #3 最优策略。
采用宽止损策略，减少被洗出次数，获取更高的年均收益和累计收益。

【历史表现】(2018-2025)
- 平均年收益率: 135.8%
- 最大回撤: -27.8%
- 收益回撤比: 4.89
- 8年累计净值: 483.5倍

================================================================================
【做多策略】
================================================================================
- 开仓日: 周三、周四（交割周周四除外）
- MA60比率范围: 99% ~ 110%
- 持仓天数: 3个交易日
- 止损: 2.0%

【做多开仓条件】
1. 当日是周三或周四
2. 收盘价/MA60 在 0.99 ~ 1.10 之间
3. 如果是交割周周四，则不开仓

================================================================================
【做空策略A】（非12月）
================================================================================
- 开仓日: 周一
- MA60比率范围: 98% ~ 110%
- 排除月份: 12月
- 持仓天数: 4个交易日
- 止损: 1.5%

【做空A开仓条件】
1. 当日是周一
2. 当前月份不是12月
3. 收盘价/MA60 在 0.98 ~ 1.10 之间

================================================================================
【做空策略B】（仅12月）
================================================================================
- 开仓日: 周五
- MA60比率上限: 100%
- 仅限月份: 12月
- 持仓天数: 5个交易日
- 止损: 2.0%

【做空B开仓条件】
1. 当日是周五
2. 当前月份是12月
3. 收盘价/MA60 <= 1.00

================================================================================
【冷静期规则】
================================================================================
- 触发条件: 单笔亏损超过20%
- 冷静期: 7个自然日内不开同方向仓位

================================================================================
【合约参数】
================================================================================
- 合约乘数: 300点
- 保证金比例: 18%
- 手续费率: 0.0023%
- 杠杆使用: 70%
- 初始资金: 100万

================================================================================
【注意事项】
================================================================================
1. 本策略基于历史数据回测，不保证未来收益
2. 股指期货交易有较高风险，请谨慎操作
3. 建议结合实际市场情况和个人风险承受能力使用
4. 交割周周四不开多仓是为了避免移仓换月带来的不确定性

================================================================================
"""
        text.insert(tk.END, strategy_text)
        text.config(state=tk.DISABLED)


def main():
    root = tk.Tk()

    # 设置DPI感知（Windows高分屏支持）
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    # 设置样式
    style = ttk.Style()
    style.theme_use('clam')

    # 设置LabelFrame标题字体大小（加大一倍）
    style.configure('TLabelframe.Label', font=('微软雅黑', 22, 'bold'))

    app = IF300SignalApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
