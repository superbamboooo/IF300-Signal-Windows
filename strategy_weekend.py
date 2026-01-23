#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
周末效应 V9 策略模块 - 创业板ETF周末效应策略
================================================================================
标的：创业板ETF (159915)
策略：利用"周末效应"，周四/周五买入 + 补充跌幅触发策略
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

# 设置中文字体
import platform
if platform.system() == 'Darwin':
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
elif platform.system() == 'Windows':
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
else:
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ==================== 策略参数（与V9一致）====================
MA30_THRESHOLD = 0.99       # MA30阈值
MA30_MAX_DIST = 0.20        # MA30最大距离
MA5_MAX_DIST = 0.05         # MA5最大距离
MA10_MAX_DIST = 0.12        # MA10最大距离
STOP_LOSS_RATE = 0.965      # 止损比例 (3.5%)
EXCLUDE_MONTHS = [12]       # 排除月份
DROP_THRESHOLD = 0.05       # 跌幅触发阈值

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


class WeekendStrategyFrame:
    """周末效应策略界面模块"""

    def __init__(self, parent):
        self.parent = parent
        self.root = parent.winfo_toplevel()

        # 数据变量
        self.df = None

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
        top_frame = ttk.LabelFrame(main_frame, text="当前市场状态 - 创业板ETF (159915)", padding="10")
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

        # 第二行：均线信息
        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="MA5:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.ma5_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ma5_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(row2, text="MA10:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.ma10_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ma10_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(row2, text="MA30:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
        self.ma30_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.ma30_var, font=('微软雅黑', 18, 'bold')).pack(side=tk.LEFT, padx=(5, 20))

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

        # 左列：周四买入条件
        left_frame = ttk.LabelFrame(signal_cols, text="周四买入条件", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.thu_weekday_var = tk.StringVar(value="星期: --")
        self.thu_weekday_label = ttk.Label(left_frame, textvariable=self.thu_weekday_var, font=('微软雅黑', 15))
        self.thu_weekday_label.pack(anchor=tk.W)

        self.thu_month_var = tk.StringVar(value="月份: --")
        self.thu_month_label = ttk.Label(left_frame, textvariable=self.thu_month_var, font=('微软雅黑', 15))
        self.thu_month_label.pack(anchor=tk.W)

        self.thu_ma_var = tk.StringVar(value="MA条件: --")
        self.thu_ma_label = ttk.Label(left_frame, textvariable=self.thu_ma_var, font=('微软雅黑', 15))
        self.thu_ma_label.pack(anchor=tk.W)

        self.thu_decline_var = tk.StringVar(value="周跌幅: --")
        self.thu_decline_label = ttk.Label(left_frame, textvariable=self.thu_decline_var, font=('微软雅黑', 15))
        self.thu_decline_label.pack(anchor=tk.W)

        self.thu_result_var = tk.StringVar(value="")
        self.thu_result_label = ttk.Label(left_frame, textvariable=self.thu_result_var, font=('微软雅黑', 18, 'bold'))
        self.thu_result_label.pack(anchor=tk.W, pady=(5, 0))

        # 中列：周五买入条件
        mid_frame = ttk.LabelFrame(signal_cols, text="周五买入条件", padding="5")
        mid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.fri_weekday_var = tk.StringVar(value="星期: --")
        self.fri_weekday_label = ttk.Label(mid_frame, textvariable=self.fri_weekday_var, font=('微软雅黑', 15))
        self.fri_weekday_label.pack(anchor=tk.W)

        self.fri_month_var = tk.StringVar(value="月份: --")
        self.fri_month_label = ttk.Label(mid_frame, textvariable=self.fri_month_var, font=('微软雅黑', 15))
        self.fri_month_label.pack(anchor=tk.W)

        self.fri_ma_var = tk.StringVar(value="MA条件: --")
        self.fri_ma_label = ttk.Label(mid_frame, textvariable=self.fri_ma_var, font=('微软雅黑', 15))
        self.fri_ma_label.pack(anchor=tk.W)

        self.fri_decline_var = tk.StringVar(value="周跌幅: --")
        self.fri_decline_label = ttk.Label(mid_frame, textvariable=self.fri_decline_var, font=('微软雅黑', 15))
        self.fri_decline_label.pack(anchor=tk.W)

        self.fri_result_var = tk.StringVar(value="")
        self.fri_result_label = ttk.Label(mid_frame, textvariable=self.fri_result_var, font=('微软雅黑', 18, 'bold'))
        self.fri_result_label.pack(anchor=tk.W, pady=(5, 0))

        # 右列：补充买入条件（5%跌幅）
        right_frame = ttk.LabelFrame(signal_cols, text="补充买入条件(5%跌幅)", padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.sup_month_var = tk.StringVar(value="月份: --")
        self.sup_month_label = ttk.Label(right_frame, textvariable=self.sup_month_var, font=('微软雅黑', 15))
        self.sup_month_label.pack(anchor=tk.W)

        self.sup_ma_var = tk.StringVar(value="MA条件: --")
        self.sup_ma_label = ttk.Label(right_frame, textvariable=self.sup_ma_var, font=('微软雅黑', 15))
        self.sup_ma_label.pack(anchor=tk.W)

        self.sup_drop_var = tk.StringVar(value="跌幅触发: --")
        self.sup_drop_label = ttk.Label(right_frame, textvariable=self.sup_drop_var, font=('微软雅黑', 15))
        self.sup_drop_label.pack(anchor=tk.W)

        self.sup_result_var = tk.StringVar(value="")
        self.sup_result_label = ttk.Label(right_frame, textvariable=self.sup_result_var, font=('微软雅黑', 18, 'bold'))
        self.sup_result_label.pack(anchor=tk.W, pady=(5, 0))

        # ===== 可开仓价格区间 =====
        price_range_frame = ttk.LabelFrame(main_frame, text="可开仓价格区间（基于MA30条件）", padding="10")
        price_range_frame.pack(fill=tk.X, pady=(0, 10))

        price_range_cols = ttk.Frame(price_range_frame)
        price_range_cols.pack(fill=tk.X)

        range_frame = ttk.Frame(price_range_cols)
        range_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(range_frame, text="买入区间:", font=('微软雅黑', 15, 'bold')).pack(side=tk.LEFT)
        self.buy_price_range_var = tk.StringVar(value="-- ~ --")
        ttk.Label(range_frame, textvariable=self.buy_price_range_var, font=('微软雅黑', 18, 'bold'), foreground='#006400').pack(side=tk.LEFT, padx=(5, 30))

        ttk.Label(range_frame, text="止损价:", font=('微软雅黑', 15, 'bold')).pack(side=tk.LEFT)
        self.stop_loss_var = tk.StringVar(value="--")
        ttk.Label(range_frame, textvariable=self.stop_loss_var, font=('微软雅黑', 18, 'bold'), foreground='#8B0000').pack(side=tk.LEFT, padx=(5, 0))

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
            file_path = os.path.join(data_path, '159915_创业板ETF_day.csv')

            if not os.path.exists(file_path):
                messagebox.showerror("错误", f"数据文件不存在:\n{file_path}")
                self.status_var.set("数据加载失败")
                return

            df = pd.read_csv(file_path, encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)

            # 计算技术指标
            df['MA5'] = df['收盘'].rolling(window=5, min_periods=5).mean()
            df['MA10'] = df['收盘'].rolling(window=10, min_periods=10).mean()
            df['MA30'] = df['收盘'].rolling(window=30, min_periods=30).mean()

            # 计算时间特征
            df['weekday'] = df['日期'].dt.weekday
            df['month'] = df['日期'].dt.month
            df['year_week'] = df['日期'].dt.strftime('%Y-%W')

            # 标记warmup期
            df['is_warmup'] = df['日期'] < pd.to_datetime('2018-01-01')

            self.df = df

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

    def get_last_week_close(self, current_date):
        """获取上周最后一个交易日的收盘价"""
        if self.df is None:
            return None

        try:
            current_idx = self.df[self.df['日期'] == current_date].index[0]
            current_week = self.df.loc[current_idx, 'year_week']

            for i in range(current_idx - 1, -1, -1):
                prev_week = self.df.loc[i, 'year_week']
                if prev_week != current_week:
                    return self.df.loc[i, '收盘']
            return None
        except:
            return None

    def get_previous_high(self, current_date, days_back=1):
        """获取N天前的最高价"""
        if self.df is None:
            return None

        try:
            current_idx = self.df[self.df['日期'] == current_date].index[0]
            if current_idx >= days_back:
                return self.df.loc[current_idx - days_back, '最高']
            return None
        except:
            return None

    def update_display(self):
        """更新界面显示"""
        if self.df is None or len(self.df) == 0:
            return

        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        current_date = latest['日期']
        price = latest['收盘']
        ma5 = latest['MA5']
        ma10 = latest['MA10']
        ma30 = latest['MA30']
        weekday = latest['weekday']
        month = latest['month']

        self.date_var.set(current_date.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.3f}")
        self.ma5_var.set(f"{ma5:.3f}" if not pd.isna(ma5) else "--")
        self.ma10_var.set(f"{ma10:.3f}" if not pd.isna(ma10) else "--")
        self.ma30_var.set(f"{ma30:.3f}" if not pd.isna(ma30) else "--")

        # 计算周跌幅
        last_week_close = self.get_last_week_close(current_date)
        if last_week_close:
            week_decline = (price - last_week_close) / last_week_close
        else:
            week_decline = None

        # 计算跌幅触发
        yesterday_high = self.get_previous_high(current_date, 1)
        day_before_high = self.get_previous_high(current_date, 2)

        self.analyze_signal(current_date, price, ma5, ma10, ma30, weekday, month, week_decline, yesterday_high, day_before_high)
        self.update_price_range(price, ma30)
        self.update_kline_chart()

    def analyze_signal(self, current_date, price, ma5, ma10, ma30, weekday, month, week_decline, yesterday_high, day_before_high):
        """分析交易信号"""
        if pd.isna(ma30) or pd.isna(ma5) or pd.isna(ma10):
            self.thu_weekday_var.set("均线数据不足")
            self.fri_weekday_var.set("均线数据不足")
            self.sup_month_var.set("均线数据不足")
            return

        # ===== 通用MA条件 =====
        ma30_ok = price > ma30 * MA30_THRESHOLD
        ma30_dist_ok = (price - ma30) / ma30 <= MA30_MAX_DIST
        ma5_dist_ok = (price - ma5) / ma5 <= MA5_MAX_DIST
        ma10_dist_ok = (price - ma10) / ma10 <= MA10_MAX_DIST
        ma_all_ok = ma30_ok and ma30_dist_ok and ma5_dist_ok and ma10_dist_ok

        month_ok = month not in EXCLUDE_MONTHS

        ma_text = f"MA条件: {'✓' if ma_all_ok else '✗'} (MA30>{MA30_THRESHOLD}, 距离≤{MA30_MAX_DIST*100:.0f}%)"

        # ===== 周四买入条件 =====
        thu_weekday_ok = weekday == 3
        self.thu_weekday_var.set(f"星期: {WEEKDAY_NAMES[weekday]} (需要周四)")
        self.thu_weekday_label.configure(foreground='green' if thu_weekday_ok else 'red')

        self.thu_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.thu_month_label.configure(foreground='green' if month_ok else 'red')

        self.thu_ma_var.set(ma_text)
        self.thu_ma_label.configure(foreground='green' if ma_all_ok else 'red')

        # 周跌幅条件
        if week_decline is not None:
            decline_pct = week_decline * 100
            thu_decline_ok = week_decline <= -0.02  # 需要跌≥2%
            self.thu_decline_var.set(f"周跌幅: {decline_pct:.2f}% (需要≤-2%)")
            self.thu_decline_label.configure(foreground='green' if thu_decline_ok else 'red')
        else:
            thu_decline_ok = False
            self.thu_decline_var.set("周跌幅: 无数据")
            self.thu_decline_label.configure(foreground='gray')

        thu_signal = thu_weekday_ok and month_ok and ma_all_ok and thu_decline_ok
        if thu_signal:
            self.thu_result_var.set("✓ 满足周四买入")
            self.thu_result_label.configure(foreground='green')
        else:
            self.thu_result_var.set("✗ 不满足")
            self.thu_result_label.configure(foreground='gray')

        # ===== 周五买入条件 =====
        fri_weekday_ok = weekday == 4
        self.fri_weekday_var.set(f"星期: {WEEKDAY_NAMES[weekday]} (需要周五)")
        self.fri_weekday_label.configure(foreground='green' if fri_weekday_ok else 'red')

        self.fri_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.fri_month_label.configure(foreground='green' if month_ok else 'red')

        self.fri_ma_var.set(ma_text)
        self.fri_ma_label.configure(foreground='green' if ma_all_ok else 'red')

        if week_decline is not None:
            self.fri_decline_var.set(f"周跌幅: {decline_pct:.2f}%")
            self.fri_decline_label.configure(foreground='blue')
        else:
            self.fri_decline_var.set("周跌幅: 无数据")
            self.fri_decline_label.configure(foreground='gray')

        fri_signal = fri_weekday_ok and month_ok and ma_all_ok
        if fri_signal:
            self.fri_result_var.set("✓ 满足周五买入")
            self.fri_result_label.configure(foreground='green')
        else:
            self.fri_result_var.set("✗ 不满足")
            self.fri_result_label.configure(foreground='gray')

        # ===== 补充买入条件（5%跌幅触发）=====
        self.sup_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.sup_month_label.configure(foreground='green' if month_ok else 'red')

        self.sup_ma_var.set(ma_text)
        self.sup_ma_label.configure(foreground='green' if ma_all_ok else 'red')

        # 检查跌幅触发
        drop_triggered = False
        drop_text = "跌幅触发: "

        if yesterday_high is not None:
            yesterday_drop = (price - yesterday_high) / yesterday_high
            if yesterday_drop <= -DROP_THRESHOLD:
                drop_triggered = True
                drop_text += f"昨日高点跌{yesterday_drop*100:.2f}%"

        if not drop_triggered and day_before_high is not None:
            day_before_drop = (price - day_before_high) / day_before_high
            if day_before_drop <= -DROP_THRESHOLD:
                drop_triggered = True
                drop_text += f"前日高点跌{day_before_drop*100:.2f}%"

        if not drop_triggered:
            drop_text += "未触发(需≤-5%)"

        self.sup_drop_var.set(drop_text)
        self.sup_drop_label.configure(foreground='green' if drop_triggered else 'red')

        sup_signal = month_ok and ma_all_ok and drop_triggered
        if sup_signal:
            self.sup_result_var.set("✓ 满足补充买入")
            self.sup_result_label.configure(foreground='green')
        else:
            self.sup_result_var.set("✗ 不满足")
            self.sup_result_label.configure(foreground='gray')

    def update_price_range(self, price, ma30):
        """计算并更新可开仓价格区间"""
        if pd.isna(ma30):
            self.buy_price_range_var.set("MA30数据不足")
            self.stop_loss_var.set("--")
            return

        # 买入区间: MA30*0.99 ~ MA30*1.20
        buy_min = ma30 * MA30_THRESHOLD
        buy_max = ma30 * (1 + MA30_MAX_DIST)
        self.buy_price_range_var.set(f"{buy_min:.3f} ~ {buy_max:.3f}")

        # 止损价
        stop_loss = price * STOP_LOSS_RATE
        self.stop_loss_var.set(f"{stop_loss:.3f} (-3.5%)")

    def update_kline_chart(self):
        """更新K线图"""
        if self.df is None or len(self.df) == 0:
            return

        self.ax.clear()
        display_df = self.df[self.df['is_warmup'] == False].tail(120).copy()
        display_df = display_df.reset_index(drop=True)
        self.kline_data = display_df

        for idx, row in display_df.iterrows():
            open_p = row['开盘']
            close_p = row['收盘']
            high_p = row['最高']
            low_p = row['最低']

            color = 'red' if close_p >= open_p else 'green'
            self.ax.plot([idx, idx], [low_p, high_p], color=color, linewidth=0.8)

            body_bottom = min(open_p, close_p)
            body_height = abs(close_p - open_p)
            rect = Rectangle((idx - 0.35, body_bottom), 0.7, body_height,
                            facecolor=color, edgecolor=color, linewidth=0.5)
            self.ax.add_patch(rect)

        # 绘制均线
        if 'MA5' in display_df.columns:
            ma5_data = display_df['MA5'].dropna()
            if len(ma5_data) > 0:
                self.ax.plot(ma5_data.index, ma5_data.values, color='orange',
                           linewidth=1, label='MA5', alpha=0.8)

        if 'MA10' in display_df.columns:
            ma10_data = display_df['MA10'].dropna()
            if len(ma10_data) > 0:
                self.ax.plot(ma10_data.index, ma10_data.values, color='purple',
                           linewidth=1, label='MA10', alpha=0.8)

        if 'MA30' in display_df.columns:
            ma30_data = display_df['MA30'].dropna()
            if len(ma30_data) > 0:
                self.ax.plot(ma30_data.index, ma30_data.values, color='blue',
                           linewidth=1.5, label='MA30', alpha=0.8)

        self.ax.set_xlim(-1, len(display_df))

        prices = display_df[['开盘', '收盘', '最高', '最低']].values.flatten()
        prices = prices[~np.isnan(prices)]
        if len(prices) > 0:
            price_min, price_max = prices.min(), prices.max()
            margin = (price_max - price_min) * 0.05
            self.ax.set_ylim(price_min - margin, price_max + margin)

        tick_step = max(1, len(display_df) // 10)
        tick_positions = list(range(0, len(display_df), tick_step))
        tick_labels = [display_df.iloc[i]['日期'].strftime('%m/%d') for i in tick_positions]
        self.ax.set_xticks(tick_positions)
        self.ax.set_xticklabels(tick_labels, rotation=45, ha='right')

        self.ax.legend(loc='upper left')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_title('创业板ETF (159915) K线图', fontsize=12)

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

        if idx > 0:
            prev_close = self.kline_data.iloc[idx-1]['收盘']
            change = close_p - prev_close
            change_pct = change / prev_close * 100
            change_str = f"{change:+.3f} ({change_pct:+.2f}%)"
        else:
            change_str = "--"

        weekday = WEEKDAY_NAMES[date.weekday()]
        text = (f"{date.strftime('%Y-%m-%d')} {weekday}\n"
                f"开: {open_p:.3f}  高: {high_p:.3f}\n"
                f"低: {low_p:.3f}  收: {close_p:.3f}\n"
                f"涨跌: {change_str}")

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

        if near_top:
            anchor_y = low_p
            offset_y = -80
            va = 'top'
        else:
            anchor_y = high_p
            offset_y = 10
            va = 'bottom'

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
            from weekend_data_updater import is_trading_time, get_etf_realtime_price

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
            self.realtime_var.set("--")
            self.realtime_label.configure(foreground='gray')

    def refresh_realtime(self):
        """获取实时行情并更新显示"""
        try:
            from weekend_data_updater import get_etf_realtime_price

            realtime = get_etf_realtime_price()
            if realtime:
                self.realtime_price = realtime
                price = realtime['price']
                time_str = realtime.get('time', '')[:5]
                source = realtime.get('source', '')

                self.realtime_var.set(f"{price:.3f} ({time_str}) [{source}]")
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
        ma5 = latest['MA5']
        ma10 = latest['MA10']
        ma30 = latest['MA30']

        self.date_var.set(today.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.3f}")

        # 计算周跌幅（使用最近数据估算）
        last_week_close = self.get_last_week_close(latest['日期'])
        if last_week_close:
            week_decline = (price - last_week_close) / last_week_close
        else:
            week_decline = None

        yesterday_high = self.get_previous_high(latest['日期'], 1)
        day_before_high = self.get_previous_high(latest['日期'], 2)

        self.analyze_signal(today, price, ma5, ma10, ma30, weekday, month, week_decline, yesterday_high, day_before_high)
        self.update_price_range(price, ma30)

    def update_data(self):
        """更新K线数据"""
        try:
            from weekend_data_updater import update_etf_data

            self.status_var.set("正在更新数据...")

            def do_update():
                try:
                    result = update_etf_data()
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
        info_window.title("周末效应 V9 策略说明")
        info_window.geometry("700x600")

        text = scrolledtext.ScrolledText(info_window, font=('微软雅黑', 10), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        strategy_text = """
================================================================================
周末效应 V9 - 创业板ETF策略
================================================================================
标的：创业板ETF (159915)
时间：2018-01-01 至今
杠杆：2.5倍融资

【历史表现】
- 年均收益: 76.4%
- 最大回撤: -18.9%
- 收益回撤比: 4.04

================================================================================
【策略参数】
================================================================================
- MA30阈值: 0.99 (价格需>MA30*0.99)
- MA30最大距离: 20%
- MA5最大距离: 5%
- MA10最大距离: 12%
- 止损率: 3.5%
- 排除月份: 12月
- 跌幅触发阈值: 5%

================================================================================
【周四买入条件】
================================================================================
1. 当日是周四
2. 非12月
3. MA条件全部满足
4. 本周跌幅≥2%
   - 跌2%~4%: 持仓5天
   - 跌4%~6%: 持仓7天
   - 跌≥6%: 持仓7天

================================================================================
【周五买入条件】
================================================================================
1. 当日是周五
2. 非12月
3. MA条件全部满足
4. 根据周涨跌和当日涨跌决定持仓天数

================================================================================
【补充买入条件】(5%跌幅触发)
================================================================================
1. 非12月
2. MA条件全部满足
3. 当前价格比昨日最高或前日最高下跌≥5%
4. 持仓2天
================================================================================
"""
        text.insert(tk.END, strategy_text)
        text.config(state=tk.DISABLED)
