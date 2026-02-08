#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 V10.14 策略模块 - 股指期货季月合约策略
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
plt.rcParams['axes.unicode_minus'] = False

# ==================== 策略参数（与V10.14一致）====================
LONG_WEEKDAYS = [2, 3]  # 周三、周四
LONG_MA_MIN = 0.99
LONG_MA_MAX = 1.10
LONG_EXCLUDE_MONTHS = []
LONG_HOLD_DAYS = 3
LONG_STOP_LOSS = 0.02

SHORT_A_WEEKDAYS = [0]  # 周一
SHORT_A_MA_MIN = 0.98
SHORT_A_MA_MAX = 1.10
SHORT_A_EXCLUDE_MONTHS = [12]
SHORT_A_HOLD_DAYS = 4
SHORT_A_STOP_LOSS = 0.015

SHORT_B_WEEKDAYS = [4]  # 周五
SHORT_B_MA_MAX = 1.00
SHORT_B_ONLY_MONTHS = [12]
SHORT_B_HOLD_DAYS = 5
SHORT_B_STOP_LOSS = 0.02

WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def get_data_path():
    """获取数据目录路径"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(os.path.dirname(base_path), 'data')
    if not os.path.exists(data_path):
        data_path = os.path.join(base_path, 'data')
    return data_path


def get_delivery_dates(start_year=2015, end_year=2030):
    """生成季月合约交割日列表"""
    delivery_dates = []
    quarterly_months = [3, 6, 9, 12]
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
    """生成所有交割周日期的集合"""
    delivery_week_set = set()
    for dd in delivery_dates:
        monday = dd - timedelta(days=4)
        for i in range(5):
            day = monday + timedelta(days=i)
            delivery_week_set.add(day)
    return delivery_week_set


class IF300StrategyFrame:
    """IF300策略界面模块"""

    def __init__(self, parent):
        self.parent = parent
        self.root = parent.winfo_toplevel()

        # 数据变量
        self.df = None
        self.delivery_dates = get_delivery_dates()
        self.delivery_week_set = get_delivery_week_dates(self.delivery_dates)

        # 实时行情相关
        self.realtime_price = None
        self.auto_refresh_id = None
        self.auto_refresh_enabled = True

        # 创建界面
        self.create_widgets()

        # 自动加载数据
        self.parent.after(100, self.load_data)

        # 启动自动刷新
        self.parent.after(2000, self.start_auto_refresh)

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 顶部信息区 =====
        top_frame = ttk.LabelFrame(main_frame, text="当前市场状态 - IF300股指期货", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # 第一行：日期和价格
        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="日期:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.date_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.date_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row1, text="星期:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.weekday_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.weekday_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row1, text="收盘价:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.price_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.price_var, font=('微软雅黑', 18, 'bold'), foreground='blue').pack(side=tk.LEFT, padx=(5, 30))

        # 右侧按钮
        ttk.Button(row1, text="更新数据", command=self.update_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(row1, text="刷新", command=self.load_data).pack(side=tk.RIGHT, padx=5)

        # 第二行：MA60和比率
        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="MA60:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.ma60_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ma60_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row2, text="价格/MA60:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.ratio_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ratio_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(row2, text="交割周:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.delivery_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.delivery_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 30))

        # 实时行情状态
        ttk.Label(row2, text="实时:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.realtime_var = tk.StringVar(value="--")
        self.realtime_label = ttk.Label(row2, textvariable=self.realtime_var, font=('微软雅黑', 15))
        self.realtime_label.pack(side=tk.LEFT, padx=(5, 0))

        # 数据更新时间
        self.refresh_time_var = tk.StringVar(value="数据更新: --")
        ttk.Label(row2, textvariable=self.refresh_time_var, font=('微软雅黑', 14), foreground='gray').pack(side=tk.RIGHT, padx=5)

        # ===== 信号显示区 =====
        signal_frame = ttk.LabelFrame(main_frame, text="交易信号条件", padding="10")
        signal_frame.pack(fill=tk.X, pady=(0, 10))

        signal_cols = ttk.Frame(signal_frame)
        signal_cols.pack(fill=tk.X)

        # 左列：做多条件
        left_frame = ttk.LabelFrame(signal_cols, text="做多条件", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.long_weekday_var = tk.StringVar(value="星期: --")
        self.long_weekday_label = ttk.Label(left_frame, textvariable=self.long_weekday_var, font=('微软雅黑', 15))
        self.long_weekday_label.pack(anchor=tk.W)

        self.long_ma_var = tk.StringVar(value="MA比率: --")
        self.long_ma_label = ttk.Label(left_frame, textvariable=self.long_ma_var, font=('微软雅黑', 15))
        self.long_ma_label.pack(anchor=tk.W)

        self.long_delivery_var = tk.StringVar(value="交割周: --")
        self.long_delivery_label = ttk.Label(left_frame, textvariable=self.long_delivery_var, font=('微软雅黑', 15))
        self.long_delivery_label.pack(anchor=tk.W)

        self.long_result_var = tk.StringVar(value="")
        self.long_result_label = ttk.Label(left_frame, textvariable=self.long_result_var, font=('微软雅黑', 18, 'bold'))
        self.long_result_label.pack(anchor=tk.W, pady=(5, 0))

        # 右列：做空条件
        right_frame = ttk.LabelFrame(signal_cols, text="做空条件", padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.short_weekday_var = tk.StringVar(value="星期: --")
        self.short_weekday_label = ttk.Label(right_frame, textvariable=self.short_weekday_var, font=('微软雅黑', 15))
        self.short_weekday_label.pack(anchor=tk.W)

        self.short_month_var = tk.StringVar(value="月份: --")
        self.short_month_label = ttk.Label(right_frame, textvariable=self.short_month_var, font=('微软雅黑', 15))
        self.short_month_label.pack(anchor=tk.W)

        self.short_ma_var = tk.StringVar(value="MA比率: --")
        self.short_ma_label = ttk.Label(right_frame, textvariable=self.short_ma_var, font=('微软雅黑', 15))
        self.short_ma_label.pack(anchor=tk.W)

        self.short_result_var = tk.StringVar(value="")
        self.short_result_label = ttk.Label(right_frame, textvariable=self.short_result_var, font=('微软雅黑', 18, 'bold'))
        self.short_result_label.pack(anchor=tk.W, pady=(5, 0))

        # ===== 可开仓价格区间 =====
        price_range_frame = ttk.LabelFrame(main_frame, text="可开仓价格区间（基于MA60条件）", padding="10")
        price_range_frame.pack(fill=tk.X, pady=(0, 10))

        price_range_cols = ttk.Frame(price_range_frame)
        price_range_cols.pack(fill=tk.X)

        long_range_frame = ttk.Frame(price_range_cols)
        long_range_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(long_range_frame, text="做多:", font=('微软雅黑', 15, 'bold')).pack(side=tk.LEFT)
        self.long_price_range_var = tk.StringVar(value="-- ~ --")
        ttk.Label(long_range_frame, textvariable=self.long_price_range_var, font=('微软雅黑', 18, 'bold'), foreground='#006400').pack(side=tk.LEFT, padx=(5, 0))

        short_range_frame = ttk.Frame(price_range_cols)
        short_range_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        ttk.Label(short_range_frame, text="做空:", font=('微软雅黑', 15, 'bold')).pack(side=tk.LEFT)
        self.short_price_range_var = tk.StringVar(value="-- ~ --")
        ttk.Label(short_range_frame, textvariable=self.short_price_range_var, font=('微软雅黑', 18, 'bold'), foreground='#8B0000').pack(side=tk.LEFT, padx=(5, 0))

        # ===== K线图区 =====
        chart_frame = ttk.LabelFrame(main_frame, text="K线图", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.kline_data = None
        self.hover_annotation = None
        self.hover_vline = None
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # ===== 底部状态栏 =====
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, font=('微软雅黑', 10)).pack(side=tk.LEFT)

        ttk.Button(status_frame, text="策略说明", command=self.show_strategy_info).pack(side=tk.RIGHT)

    def load_data(self):
        """加载K线数据"""
        self.status_var.set("正在加载数据...")
        try:
            data_path = get_data_path()
            file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

            if not os.path.exists(file_path):
                messagebox.showerror("错误", f"数据文件不存在:\n{file_path}")
                self.status_var.set("数据加载失败")
                return

            df_if = pd.read_csv(file_path, encoding='utf-8-sig')
            df_if.columns = df_if.columns.str.strip()
            df_if['日期'] = pd.to_datetime(df_if['日期'])

            # 获取价格数据
            for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
                if old_col in df_if.columns:
                    if new_col not in df_if.columns:
                        df_if[new_col] = df_if[old_col]
                    else:
                        mask = df_if[new_col].isna()
                        df_if.loc[mask, new_col] = df_if.loc[mask, old_col]

            # 尝试加载沪深300指数数据补充早期数据
            idx_file = os.path.join(data_path, 'IF_主连_沪深300股指期货_day.csv')
            if os.path.exists(idx_file):
                try:
                    df_idx = pd.read_csv(idx_file, encoding='utf-8-sig')
                    df_idx.columns = df_idx.columns.str.strip()
                    df_idx['日期'] = pd.to_datetime(df_idx['日期'])

                    for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
                        if old_col in df_idx.columns and new_col not in df_idx.columns:
                            df_idx[new_col] = df_idx[old_col]

                    if '合约' not in df_idx.columns:
                        df_idx['合约'] = 'IF主连'

                    min_date = df_if['日期'].min()
                    df_idx = df_idx[df_idx['日期'] < min_date]

                    if len(df_idx) > 0:
                        df_if = pd.concat([df_idx, df_if], ignore_index=True)
                except:
                    pass

            df_if = df_if.sort_values('日期').reset_index(drop=True)

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
                        # 计算该季月的交割日（第三个周五）
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

            # 标记warmup期
            df_if['is_warmup'] = df_if['日期'] < pd.to_datetime('2017-01-01')

            # 计算时间特征
            df_if['weekday'] = df_if['日期'].dt.weekday
            df_if['month'] = df_if['日期'].dt.month

            self.df = df_if
            self.df['MA60'] = self.df['收盘'].rolling(60).mean()

            # 更新界面
            self.update_display()

            data_start = self.df[self.df['is_warmup'] == False]['日期'].min().strftime('%Y-%m-%d')
            data_end = self.df['日期'].max().strftime('%Y-%m-%d')
            self.status_var.set(f"数据加载完成 | 数据范围: {data_start} ~ {data_end}")

            now = datetime.now().strftime('%H:%M:%S')
            self.refresh_time_var.set(f"数据更新: {now}")

        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败:\n{str(e)}")
            self.status_var.set("数据加载失败")

    def update_display(self):
        """更新界面显示"""
        if self.df is None or len(self.df) == 0:
            return

        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        current_date = datetime.now()  # 改为显示今天日期，而不是数据的最后日期
        price = latest['收盘']
        ma60 = latest['MA60']
        weekday = current_date.weekday()  # 改为用今天的weekday
        month = current_date.month  # 改为用今天的month

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

        is_delivery_week = current_date in self.delivery_week_set
        self.delivery_var.set("是" if is_delivery_week else "否")

        self.analyze_signal(current_date, price, ma60, weekday, month, is_delivery_week)
        self.update_price_range(month)
        self.update_kline_chart()

    def analyze_signal(self, current_date, price, ma60, weekday, month, is_delivery_week):
        """分析交易信号"""
        if pd.isna(ma60):
            self.long_weekday_var.set("MA60数据不足")
            self.long_ma_var.set("")
            self.long_delivery_var.set("")
            self.short_weekday_var.set("MA60数据不足")
            self.short_month_var.set("")
            self.short_ma_var.set("")
            return

        ratio = price / ma60

        # ===== 做多条件分析 =====
        long_weekday_ok = weekday in LONG_WEEKDAYS
        weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (需要周三/周四)"
        self.long_weekday_var.set(weekday_text)
        self.long_weekday_label.configure(foreground='green' if long_weekday_ok else 'red')

        long_ma_ok = LONG_MA_MIN <= ratio <= LONG_MA_MAX
        ma_text = f"MA比率: {ratio:.4f} (需要{LONG_MA_MIN}~{LONG_MA_MAX})"
        self.long_ma_var.set(ma_text)
        self.long_ma_label.configure(foreground='green' if long_ma_ok else 'red')

        long_delivery_ok = not (is_delivery_week and weekday == 3)
        delivery_text = f"交割周周四: {'是(不可开仓)' if not long_delivery_ok else '否'}"
        self.long_delivery_var.set(delivery_text)
        self.long_delivery_label.configure(foreground='green' if long_delivery_ok else 'red')

        long_signal = long_weekday_ok and long_ma_ok and long_delivery_ok
        if long_signal:
            self.long_result_var.set("✓ 满足做多条件")
            self.long_result_label.configure(foreground='green')
        else:
            self.long_result_var.set("✗ 不满足做多条件")
            self.long_result_label.configure(foreground='gray')

        # ===== 做空条件分析 =====
        if month == 12:
            short_weekday_ok = weekday in SHORT_B_WEEKDAYS
            weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (12月需要周五)"
            short_ma_ok = ratio <= SHORT_B_MA_MAX
            ma_text = f"MA比率: {ratio:.4f} (需要≤{SHORT_B_MA_MAX})"
        else:
            short_weekday_ok = weekday in SHORT_A_WEEKDAYS
            weekday_text = f"星期: {WEEKDAY_NAMES[weekday]} (非12月需要周一)"
            short_ma_ok = SHORT_A_MA_MIN <= ratio <= SHORT_A_MA_MAX
            ma_text = f"MA比率: {ratio:.4f} (需要{SHORT_A_MA_MIN}~{SHORT_A_MA_MAX})"

        self.short_weekday_var.set(weekday_text)
        self.short_weekday_label.configure(foreground='green' if short_weekday_ok else 'red')

        month_text = f"月份: {month}月 ({'12月策略B' if month == 12 else '非12月策略A'})"
        self.short_month_var.set(month_text)
        self.short_month_label.configure(foreground='blue')

        self.short_ma_var.set(ma_text)
        self.short_ma_label.configure(foreground='green' if short_ma_ok else 'red')

        short_signal = short_weekday_ok and short_ma_ok
        if short_signal:
            self.short_result_var.set("✓ 满足做空条件")
            self.short_result_label.configure(foreground='red')
        else:
            self.short_result_var.set("✗ 不满足做空条件")
            self.short_result_label.configure(foreground='gray')

    def update_price_range(self, month):
        """计算并更新可开仓价格区间"""
        if self.df is None or len(self.df) == 0:
            return

        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        ma60 = latest['MA60']

        if pd.isna(ma60):
            self.long_price_range_var.set("MA60数据不足")
            self.short_price_range_var.set("MA60数据不足")
            return

        long_min = ma60 * LONG_MA_MIN
        long_max = ma60 * LONG_MA_MAX
        self.long_price_range_var.set(f"{long_min:.2f} ~ {long_max:.2f}")

        if month == 12:
            short_max = ma60 * SHORT_B_MA_MAX
            self.short_price_range_var.set(f"≤ {short_max:.2f}")
        else:
            short_min = ma60 * SHORT_A_MA_MIN
            short_max = ma60 * SHORT_A_MA_MAX
            self.short_price_range_var.set(f"{short_min:.2f} ~ {short_max:.2f}")

    def update_kline_chart(self):
        """更新K线图"""
        if self.df is None or len(self.df) == 0:
            return

        self.ax.clear()
        display_df = self.df[self.df['is_warmup'] == False].tail(120).copy()
        display_df = display_df.reset_index(drop=True)
        self.kline_data = display_df

        # 获取价格范围用于绘制标记
        price_min = display_df['最低'].min()
        price_max = display_df['最高'].max()
        price_range = price_max - price_min

        # 绘制K线
        width = 0.6
        for idx, row in display_df.iterrows():
            open_p = row['开盘']
            close_p = row['收盘']
            high_p = row['最高']
            low_p = row['最低']

            # 确定颜色：涨红跌绿
            if close_p >= open_p:
                color = 'red'
                body_bottom = open_p
                body_height = close_p - open_p
            else:
                color = 'green'
                body_bottom = close_p
                body_height = open_p - close_p

            # 绘制影线
            self.ax.plot([idx, idx], [low_p, high_p], color=color, linewidth=1)

            # 绘制实体
            rect = Rectangle((idx - width/2, body_bottom), width, body_height if body_height > 0 else 0.1,
                            facecolor=color, edgecolor=color, linewidth=1)
            self.ax.add_patch(rect)

        # 绘制MA60均线
        if 'MA60' in display_df.columns:
            ma60_data = display_df['MA60'].dropna()
            if len(ma60_data) > 0:
                ma60_indices = display_df.loc[ma60_data.index].index.tolist()
                self.ax.plot(ma60_indices, ma60_data.values, color='blue', linewidth=1.5, label='MA60')

        # 绘制合约分割线和标注合约名称
        if '合约' in display_df.columns:
            contracts = display_df['合约'].tolist()
            contract_ranges = []
            current_contract = contracts[0] if contracts else ''
            start_idx = 0

            for i, contract in enumerate(contracts):
                if contract != current_contract and contract != '':
                    if current_contract:
                        contract_ranges.append((start_idx, i - 1, current_contract))
                    start_idx = i
                    current_contract = contract

            if current_contract:
                contract_ranges.append((start_idx, len(contracts) - 1, current_contract))

            # 标注合约名称
            for start, end, contract in contract_ranges:
                mid_pos = (start + end) / 2
                self.ax.text(mid_pos, price_max + price_range * 0.02, contract,
                            fontsize=9, color='purple', ha='center', va='bottom', fontweight='bold')

        # 绘制交割周黄色背景
        for i, row in display_df.iterrows():
            date = row['日期']
            if date in self.delivery_week_set:
                rect = Rectangle((i - 0.5, price_min - price_range * 0.02),
                                1, price_range * 1.04,
                                facecolor='yellow', alpha=0.15, edgecolor='orange',
                                linestyle='--', linewidth=0.5)
                self.ax.add_patch(rect)

        # 在K线下方显示星期几
        weekday_chars = ['一', '二', '三', '四', '五', '六', '日']
        for i, row in display_df.iterrows():
            wd = row['weekday']
            self.ax.text(i, price_min - price_range * 0.03, weekday_chars[wd],
                        fontsize=7, color='gray', ha='center', va='top')

        # 设置X轴标签
        step = max(1, len(display_df) // 6)
        tick_positions = list(range(0, len(display_df), step))
        tick_labels = [display_df.iloc[i]['日期'].strftime('%m-%d') for i in tick_positions]
        self.ax.set_xticks(tick_positions)
        self.ax.set_xticklabels(tick_labels, fontsize=8)

        # 设置Y轴
        self.ax.set_ylabel('价格', fontsize=9)
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
        self.ax.legend(handles=legend_elements, loc='upper left', fontsize=8)

        # 设置标题
        latest_date = display_df.iloc[-1]['日期'].strftime('%Y-%m-%d')
        latest_contract = display_df.iloc[-1].get('合约', '未知') if '合约' in display_df.columns else '未知'
        if not latest_contract:
            latest_contract = '未知'
        self.ax.set_title(f'IF300 季月合约K线图 [{latest_contract}] (截至 {latest_date})', fontsize=10)

        # 调整Y轴范围给合约标注和星期留空间
        self.ax.set_ylim(price_min - price_range * 0.08, price_max + price_range * 0.1)

        # 调整边距
        self.fig.tight_layout()
        self.hover_annotation = None
        self.hover_vline = None
        self.canvas.draw()

    def on_mouse_move(self, event):
        """鼠标移动事件处理"""
        if event.inaxes != self.ax or self.kline_data is None:
            if self.hover_annotation is not None:
                self.hover_annotation.set_visible(False)
            if self.hover_vline is not None:
                self.hover_vline.set_visible(False)
            self.canvas.draw_idle()
            return

        x = event.xdata
        if x is None:
            return

        idx = int(round(x))
        if idx < 0 or idx >= len(self.kline_data):
            return

        row = self.kline_data.iloc[idx]
        date = row['日期']
        open_p = row['开盘']
        high_p = row['最高']
        low_p = row['最低']
        close_p = row['收盘']
        contract = row.get('合约', '')

        if idx > 0:
            prev_close = self.kline_data.iloc[idx-1]['收盘']
            change = close_p - prev_close
            change_pct = change / prev_close * 100
            change_str = f"{change:+.2f} ({change_pct:+.2f}%)"
        else:
            change_str = "--"

        weekday = WEEKDAY_NAMES[date.weekday()]

        # 获取MA60数据
        ma60_value = row.get('MA60', None)
        if pd.notna(ma60_value):
            ma60_str = f"\nMA60: {ma60_value:.2f}"
        else:
            ma60_str = ""

        text = (f"{date.strftime('%Y-%m-%d')} {weekday}\n"
                f"合约: {contract}\n"
                f"开: {open_p:.2f}  高: {high_p:.2f}\n"
                f"低: {low_p:.2f}  收: {close_p:.2f}\n"
                f"涨跌: {change_str}{ma60_str}")

        # 智能tooltip位置
        data_len = len(self.kline_data)
        near_right = idx > data_len * 0.75

        if near_right:
            offset_x = -10
            ha = 'right'
        else:
            offset_x = 10
            ha = 'left'

        y_min, y_max = self.ax.get_ylim()
        y_range = y_max - y_min
        near_top = high_p > y_min + y_range * 0.75
        near_bottom = low_p < y_min + y_range * 0.25  # 检查是否靠近底部

        if near_top:
            # 靠近顶部，tooltip显示在下方（距离近一些）
            anchor_y = low_p
            offset_y = 10
            va = 'top'
        elif near_bottom:
            # 靠近底部，tooltip显示在上方
            anchor_y = high_p
            offset_y = -10
            va = 'bottom'
        else:
            # 中间位置，tooltip显示在下方
            anchor_y = high_p
            offset_y = 10
            va = 'top'

        if self.hover_annotation is None:
            self.hover_annotation = self.ax.annotate(
                text, xy=(idx, anchor_y), xytext=(offset_x, offset_y),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', edgecolor='gray', alpha=0.95),
                fontsize=9, ha=ha, va=va
            )
        else:
            self.hover_annotation.set_text(text)
            self.hover_annotation.xy = (idx, anchor_y)
            self.hover_annotation.xyann = (offset_x, offset_y)
            self.hover_annotation.set_ha(ha)
            self.hover_annotation.set_va(va)
            self.hover_annotation.set_visible(True)

        if self.hover_vline is None:
            self.hover_vline = self.ax.axvline(x=idx, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
        else:
            self.hover_vline.set_xdata([idx, idx])
            self.hover_vline.set_visible(True)

        self.canvas.draw_idle()

    def start_auto_refresh(self):
        """启动自动刷新"""
        try:
            from data_updater import is_trading_time, get_realtime_price

            is_trading_day, is_trading_hours, _ = is_trading_time()

            if is_trading_day and is_trading_hours and self.auto_refresh_enabled:
                self.refresh_realtime()
                self.auto_refresh_id = self.parent.after(60000, self.start_auto_refresh)
                self.realtime_var.set("自动刷新中...")
                self.realtime_label.configure(foreground='green')
            elif is_trading_day and not is_trading_hours:
                now = datetime.now()
                if now.hour < 9 or (now.hour == 9 and now.minute < 30):
                    self.realtime_var.set("盘前等待")
                elif now.hour >= 15:
                    self.realtime_var.set("已收盘")
                else:
                    self.realtime_var.set("午休")
                self.realtime_label.configure(foreground='gray')
                self.auto_refresh_id = self.parent.after(300000, self.start_auto_refresh)
            else:
                self.realtime_var.set("休市")
                self.realtime_label.configure(foreground='gray')
        except Exception as e:
            self.realtime_var.set("错误")
            self.realtime_label.configure(foreground='red')

    def refresh_realtime(self):
        """获取实时行情并更新显示"""
        try:
            from data_updater import get_realtime_price

            realtime = get_realtime_price()
            if realtime:
                self.realtime_price = realtime
                price = realtime['price']
                time_str = realtime['time'][:5]
                source = realtime.get('source', '')

                self.realtime_var.set(f"{price:.2f} ({time_str}) [{source}]")
                self.realtime_label.configure(foreground='green')

                now = datetime.now().strftime('%H:%M:%S')
                self.refresh_time_var.set(f"数据更新: {now}")

                self.update_display_realtime()
            else:
                self.realtime_var.set("获取失败")
                self.realtime_label.configure(foreground='red')
        except Exception as e:
            self.realtime_var.set("错误")
            self.realtime_label.configure(foreground='red')

    def update_display_realtime(self):
        """使用系统时钟和实时行情更新信号显示"""
        if self.df is None or len(self.df) == 0 or self.realtime_price is None:
            return

        today = datetime.now()
        weekday = today.weekday()
        month = today.month

        price = self.realtime_price['price']
        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        ma60 = latest['MA60']

        self.date_var.set(today.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.2f}")

        if not pd.isna(ma60):
            ratio = price / ma60
            self.ratio_var.set(f"{ratio:.4f} ({ratio*100:.2f}%)")
        else:
            ratio = None

        is_delivery_week = today in self.delivery_week_set or pd.Timestamp(today.date()) in self.delivery_week_set
        self.delivery_var.set("是" if is_delivery_week else "否")

        self.analyze_signal(today, price, ma60, weekday, month, is_delivery_week)

    def update_data(self):
        """更新K线数据"""
        try:
            from data_updater import update_if_data

            self.status_var.set("正在更新数据...")

            def do_update():
                try:
                    result = update_if_data()
                    self.parent.after(0, lambda: self.on_update_complete(result))
                except Exception as e:
                    self.parent.after(0, lambda: self.on_update_error(str(e)))

            thread = threading.Thread(target=do_update)
            thread.start()

        except ImportError:
            messagebox.showinfo("提示", "数据更新模块未安装。")

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

        text = scrolledtext.ScrolledText(info_window, font=('微软雅黑', 10), wrap=tk.WORD)
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

================================================================================
【做空策略A】（非12月）
================================================================================
- 开仓日: 周一
- MA60比率范围: 98% ~ 110%
- 持仓天数: 4个交易日
- 止损: 1.5%

================================================================================
【做空策略B】（仅12月）
================================================================================
- 开仓日: 周五
- MA60比率范围: ≤100%
- 持仓天数: 5个交易日
- 止损: 2.0%
================================================================================
"""
        text.insert(tk.END, strategy_text)
        text.config(state=tk.DISABLED)
