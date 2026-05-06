#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
周末效应 V10.02 策略模块 - 创业板ETF周末效应策略
================================================================================
标的：创业板ETF (159915)
策略：
1. 保留原 v9 的周四 / 周五策略
2. 策略1升级为两段式 3%/4% 回撤买入
3. 卖点升级为 v10.02 组合版反弹卖点
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

# 导入统一的路径管理模块
from path_manager import get_data_path

# ==================== 策略参数（V10.02）====================
MA30_THRESHOLD = 0.99       # MA30阈值
MA30_MAX_DIST = 0.20        # MA30最大距离
MA5_MAX_DIST = 0.05         # MA5最大距离
MA10_MAX_DIST = 0.12        # MA10最大距离
EXCLUDE_MONTHS = [12]       # 排除月份

ORIGINAL_STOP_LOSS_RATE = 0.965        # 原周四/周五策略止损 3.5%
STRATEGY1_STOP_LOSS_RATE = 0.975       # 策略1止损 2.5%

STRATEGY1_FIRST_STAGE = 0.03           # 3% 回撤
STRATEGY1_SECOND_STAGE = 0.04          # 4% 回撤
STRATEGY1_HOLD_TRADING_DAYS = 3        # 持有 3TD

STRATEGY1_REBOUND_LOOKBACK = 3
STRATEGY1_REBOUND_THRESHOLD = 0.08
STRATEGY1_REBOUND_MIN_HOLD = 3

ORIGINAL_REBOUND_LOOKBACK = 1
ORIGINAL_REBOUND_THRESHOLD = 0.05
ORIGINAL_REBOUND_MIN_HOLD = 2

WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


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

        ttk.Label(row1, text="当前价:", font=('微软雅黑', 15)).pack(side=tk.LEFT)
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

        # 右列：策略1两段式买入
        right_frame = ttk.LabelFrame(signal_cols, text="策略1 两段式买入 (V10.02)", padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.sup_month_var = tk.StringVar(value="月份: --")
        self.sup_month_label = ttk.Label(right_frame, textvariable=self.sup_month_var, font=('微软雅黑', 15))
        self.sup_month_label.pack(anchor=tk.W)

        self.sup_ma_var = tk.StringVar(value="MA条件: --")
        self.sup_ma_label = ttk.Label(right_frame, textvariable=self.sup_ma_var, font=('微软雅黑', 15))
        self.sup_ma_label.pack(anchor=tk.W)

        self.sup_ref_var = tk.StringVar(value="参考价/回撤线: --")
        self.sup_ref_label = ttk.Label(right_frame, textvariable=self.sup_ref_var, font=('微软雅黑', 15))
        self.sup_ref_label.pack(anchor=tk.W)

        self.sup_drop_var = tk.StringVar(value="触发状态: --")
        self.sup_drop_label = ttk.Label(right_frame, textvariable=self.sup_drop_var, font=('微软雅黑', 15))
        self.sup_drop_label.pack(anchor=tk.W)

        self.sup_entry_var = tk.StringVar(value="策略1买点: --")
        self.sup_entry_label = ttk.Label(right_frame, textvariable=self.sup_entry_var, font=('微软雅黑', 15))
        self.sup_entry_label.pack(anchor=tk.W)

        self.sup_result_var = tk.StringVar(value="")
        self.sup_result_label = ttk.Label(right_frame, textvariable=self.sup_result_var, font=('微软雅黑', 18, 'bold'))
        self.sup_result_label.pack(anchor=tk.W, pady=(5, 0))

        # ===== 可开仓价格区间与卖点规则 =====
        price_range_frame = ttk.LabelFrame(main_frame, text="参考买卖规则", padding="10")
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
        ttk.Label(range_frame, textvariable=self.stop_loss_var, font=('微软雅黑', 15, 'bold'), foreground='#8B0000').pack(side=tk.LEFT, padx=(5, 0))

        sell_frame = ttk.Frame(price_range_frame)
        sell_frame.pack(fill=tk.X, pady=(8, 0))

        self.sell_rule_var = tk.StringVar(value="策略1卖点: --")
        ttk.Label(sell_frame, textvariable=self.sell_rule_var, font=('微软雅黑', 14)).pack(anchor=tk.W)

        self.sell_rule2_var = tk.StringVar(value="周四/周五卖点: --")
        ttk.Label(sell_frame, textvariable=self.sell_rule2_var, font=('微软雅黑', 14)).pack(anchor=tk.W)

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

    def get_last_week_close_by_index(self, current_idx):
        """基于索引获取上周最后一个交易日收盘价"""
        if self.df is None or current_idx is None or current_idx <= 0:
            return None

        try:
            current_week = self.df.loc[current_idx, 'year_week']
            for i in range(current_idx - 1, -1, -1):
                if self.df.loc[i, 'year_week'] != current_week:
                    return self.df.loc[i, '收盘']
            return None
        except Exception:
            return None

    def get_previous_high_by_index(self, current_idx, days_back=1):
        """基于索引获取N天前的最高价"""
        if self.df is None or current_idx is None:
            return None

        try:
            target_idx = current_idx - days_back
            if target_idx >= 0:
                return self.df.loc[target_idx, '最高']
            return None
        except Exception:
            return None

    def get_previous_close_by_index(self, current_idx, days_back=1):
        """基于索引获取N天前的收盘价"""
        if self.df is None or current_idx is None:
            return None

        try:
            target_idx = current_idx - days_back
            if target_idx >= 0:
                return self.df.loc[target_idx, '收盘']
            return None
        except Exception:
            return None

    def _evaluate_ma_filters(self, entry_price, ma5, ma10, ma30):
        """评估均线过滤条件"""
        if any(pd.isna(v) for v in [entry_price, ma5, ma10, ma30]):
            return {
                'valid': False,
                'ma30_ok': False,
                'ma30_dist_ok': False,
                'ma5_dist_ok': False,
                'ma10_dist_ok': False,
                'text': 'MA条件: 数据不足',
            }

        ma30_ok = entry_price > ma30 * MA30_THRESHOLD
        ma30_dist_ok = (entry_price - ma30) / ma30 <= MA30_MAX_DIST
        ma5_dist_ok = (entry_price - ma5) / ma5 <= MA5_MAX_DIST
        ma10_dist_ok = (entry_price - ma10) / ma10 <= MA10_MAX_DIST
        valid = ma30_ok and ma30_dist_ok and ma5_dist_ok and ma10_dist_ok

        text = (
            f"MA条件: {'✓' if valid else '✗'} "
            f"(>{MA30_THRESHOLD:.2f}×MA30, MA30≤{MA30_MAX_DIST*100:.0f}%, "
            f"MA5≤{MA5_MAX_DIST*100:.0f}%, MA10≤{MA10_MAX_DIST*100:.0f}%)"
        )

        return {
            'valid': valid,
            'ma30_ok': ma30_ok,
            'ma30_dist_ok': ma30_dist_ok,
            'ma5_dist_ok': ma5_dist_ok,
            'ma10_dist_ok': ma10_dist_ok,
            'text': text,
        }

    def update_display(self):
        """更新界面显示"""
        if self.df is None or len(self.df) == 0:
            return

        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        latest_idx = latest.name
        price = latest['收盘']
        current_date = latest['日期']
        weekday = int(latest['weekday'])
        month = int(latest['month'])
        previous_close = self.get_previous_close_by_index(latest_idx, 1)
        last_week_close = self.get_last_week_close_by_index(latest_idx)
        week_decline = ((price - last_week_close) / last_week_close) if last_week_close else None

        yesterday_high = self.get_previous_high_by_index(latest_idx, 1)
        day_before_high = self.get_previous_high_by_index(latest_idx, 2)

        close_ma_values = {
            'ma5': latest['MA5'],
            'ma10': latest['MA10'],
            'ma30': latest['MA30'],
        }
        prev_row = self.df.iloc[latest_idx - 1] if latest_idx >= 1 else latest
        strategy1_ma_values = {
            'ma5': prev_row['MA5'],
            'ma10': prev_row['MA10'],
            'ma30': prev_row['MA30'],
        }

        self.date_var.set(current_date.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.3f}")
        self.ma5_var.set(f"{close_ma_values['ma5']:.3f}" if not pd.isna(close_ma_values['ma5']) else "--")
        self.ma10_var.set(f"{close_ma_values['ma10']:.3f}" if not pd.isna(close_ma_values['ma10']) else "--")
        self.ma30_var.set(f"{close_ma_values['ma30']:.3f}" if not pd.isna(close_ma_values['ma30']) else "--")

        self.analyze_signal(
            signal_date=current_date,
            price=price,
            open_price=latest['开盘'],
            high_price=latest['最高'],
            low_price=latest['最低'],
            previous_close=previous_close,
            close_ma_values=close_ma_values,
            strategy1_ma_values=strategy1_ma_values,
            weekday=weekday,
            month=month,
            week_decline=week_decline,
            yesterday_high=yesterday_high,
            day_before_high=day_before_high,
            close_confirmed=True,
            realtime_mode=False,
        )
        self.update_price_range(price, close_ma_values['ma30'])
        self.update_kline_chart()

    def analyze_signal(
        self,
        signal_date,
        price,
        open_price,
        high_price,
        low_price,
        previous_close,
        close_ma_values,
        strategy1_ma_values,
        weekday,
        month,
        week_decline,
        yesterday_high,
        day_before_high,
        close_confirmed=True,
        realtime_mode=False,
    ):
        """分析交易信号"""
        close_ma = self._evaluate_ma_filters(
            price,
            close_ma_values['ma5'],
            close_ma_values['ma10'],
            close_ma_values['ma30'],
        )

        if close_ma_values['ma30'] is None or pd.isna(close_ma_values['ma30']):
            self.thu_weekday_var.set("均线数据不足")
            self.fri_weekday_var.set("均线数据不足")
            self.sup_month_var.set("均线数据不足")
            return

        month_ok = month not in EXCLUDE_MONTHS
        mode_hint = "（实时估算）" if realtime_mode else ""

        # ===== 周四买入条件 =====
        thu_weekday_ok = weekday == 3
        self.thu_weekday_var.set(f"星期: {WEEKDAY_NAMES[weekday]} (需要周四)")
        self.thu_weekday_label.configure(foreground='green' if thu_weekday_ok else 'red')

        self.thu_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.thu_month_label.configure(foreground='green' if month_ok else 'red')

        self.thu_ma_var.set(f"{close_ma['text']}{mode_hint}")
        self.thu_ma_label.configure(foreground='green' if close_ma['valid'] else 'red')

        # 周跌幅条件
        if week_decline is not None:
            decline_pct = week_decline * 100
            if week_decline <= -0.06:
                thu_subtype = "thursday_6plus"
                thu_decline_text = f"周跌幅: {decline_pct:.2f}% (≥6%，下周四卖)"
            elif week_decline <= -0.04:
                thu_subtype = "thursday_4_6"
                thu_decline_text = f"周跌幅: {decline_pct:.2f}% (4%-6%，下周四卖)"
            elif week_decline <= -0.02:
                thu_subtype = "thursday_2_4"
                thu_decline_text = f"周跌幅: {decline_pct:.2f}% (2%-4%，下周二卖)"
            else:
                thu_subtype = None
                thu_decline_text = f"周跌幅: {decline_pct:.2f}% (未达2%)"

            self.thu_decline_var.set(thu_decline_text)
            self.thu_decline_label.configure(foreground='green' if thu_subtype else 'red')
        else:
            thu_subtype = None
            self.thu_decline_var.set("周跌幅: 无数据")
            self.thu_decline_label.configure(foreground='gray')

        thu_signal = thu_weekday_ok and month_ok and close_ma['valid'] and thu_subtype is not None
        if thu_signal:
            self.thu_result_var.set(f"✓ 满足周四买入：{thu_subtype}")
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

        self.fri_ma_var.set(f"{close_ma['text']}{mode_hint}")
        self.fri_ma_label.configure(foreground='green' if close_ma['valid'] else 'red')

        day_change = None
        if previous_close and previous_close != 0:
            day_change = (price - previous_close) / previous_close

        if week_decline is not None and day_change is not None:
            if week_decline < -0.03:
                fri_subtype = "friday_week_down"
                fri_text = f"周跌幅 {week_decline*100:.2f}% (下周四卖)"
            elif day_change < -0.03:
                fri_subtype = "friday_day_down"
                fri_text = f"周五涨跌 {day_change*100:.2f}% (下周三卖)"
            elif day_change > 0.03 and week_decline > 0.05:
                fri_subtype = "friday_strong"
                fri_text = f"周强势: 日涨{day_change*100:.2f}%, 周涨{week_decline*100:.2f}% (下周一卖)"
            else:
                fri_subtype = "friday_normal"
                fri_text = f"周跌幅 {week_decline*100:.2f}%, 日涨跌 {day_change*100:.2f}% (下周一卖)"

            self.fri_decline_var.set(fri_text)
            self.fri_decline_label.configure(foreground='green' if fri_subtype else 'red')
        else:
            fri_subtype = None
            self.fri_decline_var.set("周跌幅: 无数据")
            self.fri_decline_label.configure(foreground='gray')

        fri_signal = fri_weekday_ok and month_ok and close_ma['valid'] and fri_subtype is not None
        if fri_signal:
            self.fri_result_var.set(f"✓ 满足周五买入：{fri_subtype}")
            self.fri_result_label.configure(foreground='green')
        else:
            self.fri_result_var.set("✗ 不满足")
            self.fri_result_label.configure(foreground='gray')

        # ===== 策略1：两段式 3%/4% 回撤 =====
        self.sup_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.sup_month_label.configure(foreground='green' if month_ok else 'red')

        reference_candidates = []
        if yesterday_high is not None and not pd.isna(yesterday_high):
            reference_candidates.append(("昨高", yesterday_high))
        if day_before_high is not None and not pd.isna(day_before_high):
            reference_candidates.append(("前高", day_before_high))
        if open_price is not None and not pd.isna(open_price):
            reference_candidates.append(("今开", open_price))

        if not reference_candidates:
            self.sup_ma_var.set("MA条件: 数据不足")
            self.sup_ma_label.configure(foreground='gray')
            self.sup_ref_var.set("参考价/回撤线: 无数据")
            self.sup_ref_label.configure(foreground='gray')
            self.sup_drop_var.set("触发状态: 无法判断")
            self.sup_drop_label.configure(foreground='gray')
            self.sup_entry_var.set("策略1买点: --")
            self.sup_entry_label.configure(foreground='gray')
            self.sup_result_var.set("✗ 不满足")
            self.sup_result_label.configure(foreground='gray')
            return

        ref_label, reference_price = max(reference_candidates, key=lambda item: item[1])
        first_stage_price = reference_price * (1 - STRATEGY1_FIRST_STAGE)
        second_stage_price = reference_price * (1 - STRATEGY1_SECOND_STAGE)

        self.sup_ref_var.set(
            f"参考价: {ref_label}={reference_price:.3f} | 3%线={first_stage_price:.3f} | 4%线={second_stage_price:.3f}"
        )
        self.sup_ref_label.configure(foreground='blue')

        strategy1_entry_price = None
        strategy1_trigger_text = "触发状态: 未到3%线"
        strategy1_entry_text = "策略1买点: 未到3%线"
        strategy1_triggered = False

        if open_price <= second_stage_price:
            strategy1_entry_price = open_price
            strategy1_trigger_text = f"触发状态: 开盘直接低于4%线，按开盘价 {open_price:.3f}"
            strategy1_entry_text = f"策略1买点: 开盘价 {open_price:.3f}"
            strategy1_triggered = True
        elif low_price <= second_stage_price:
            strategy1_entry_price = second_stage_price
            strategy1_trigger_text = f"触发状态: 盘中触达4%线，按4%线 {second_stage_price:.3f}"
            strategy1_entry_text = f"策略1买点: 4%线 {second_stage_price:.3f}"
            strategy1_triggered = True
        elif low_price <= first_stage_price:
            if close_confirmed:
                if price >= first_stage_price:
                    strategy1_entry_price = first_stage_price
                    strategy1_trigger_text = f"触发状态: 收盘重新站回3%线，按3%线 {first_stage_price:.3f}"
                    strategy1_entry_text = f"策略1买点: 3%线 {first_stage_price:.3f}"
                    strategy1_triggered = True
                else:
                    strategy1_trigger_text = "触发状态: 跌到3%-4%区间，但收盘未站回3%线"
                    strategy1_entry_text = "策略1买点: 收盘未站回3%线，今日放弃"
            else:
                if price >= first_stage_price:
                    strategy1_trigger_text = "触发状态: 已回到3%线之上，需收盘确认后才能按3%线买入"
                    strategy1_entry_text = f"策略1买点: 若收盘确认，将按3%线 {first_stage_price:.3f}"
                else:
                    strategy1_trigger_text = "触发状态: 已进入3%-4%区间，继续观察4%线或收盘回到3%线"
                    strategy1_entry_text = f"策略1买点: 候选3%线 {first_stage_price:.3f} / 4%线 {second_stage_price:.3f}"

        strategy1_check_price = strategy1_entry_price if strategy1_entry_price is not None else price
        strategy1_ma = self._evaluate_ma_filters(
            strategy1_check_price,
            strategy1_ma_values['ma5'],
            strategy1_ma_values['ma10'],
            strategy1_ma_values['ma30'],
        )

        ma_hint = "（以前一交易日均线检查）" if not realtime_mode else "（按前一交易日均线实时估算）"
        self.sup_ma_var.set(f"{strategy1_ma['text']}{ma_hint}")
        self.sup_ma_label.configure(foreground='green' if strategy1_ma['valid'] else 'red')

        self.sup_drop_var.set(strategy1_trigger_text)
        self.sup_drop_label.configure(foreground='green' if strategy1_triggered else '#CC7A00')
        self.sup_entry_var.set(strategy1_entry_text)
        self.sup_entry_label.configure(foreground='green' if strategy1_triggered else '#1F4E79')

        strategy1_signal = month_ok and strategy1_ma['valid'] and strategy1_triggered
        if strategy1_signal:
            self.sup_result_var.set("✓ 满足策略1买入")
            self.sup_result_label.configure(foreground='green')
        else:
            self.sup_result_var.set("✗ 不满足")
            self.sup_result_label.configure(foreground='gray')

    def update_price_range(self, price, ma30):
        """计算并更新可开仓价格区间"""
        if pd.isna(ma30):
            self.buy_price_range_var.set("MA30数据不足")
            self.stop_loss_var.set("--")
            self.sell_rule_var.set("策略1卖点: --")
            self.sell_rule2_var.set("周四/周五卖点: --")
            return

        # 买入区间: MA30*0.99 ~ MA30*1.20
        buy_min = ma30 * MA30_THRESHOLD
        buy_max = ma30 * (1 + MA30_MAX_DIST)
        self.buy_price_range_var.set(f"{buy_min:.3f} ~ {buy_max:.3f}")

        strategy1_stop = price * STRATEGY1_STOP_LOSS_RATE
        original_stop = price * ORIGINAL_STOP_LOSS_RATE
        self.stop_loss_var.set(
            f"策略1 {strategy1_stop:.3f} (-2.5%) | 周四/周五 {original_stop:.3f} (-3.5%)"
        )

        self.sell_rule_var.set(
            f"策略1卖点: 前{STRATEGY1_REBOUND_LOOKBACK}日低点反弹{int(STRATEGY1_REBOUND_THRESHOLD*100)}%，盘中卖，最短持有{STRATEGY1_REBOUND_MIN_HOLD}TD"
        )
        self.sell_rule2_var.set(
            f"周四/周五卖点: 前{ORIGINAL_REBOUND_LOOKBACK}日低点反弹{int(ORIGINAL_REBOUND_THRESHOLD*100)}%，盘中卖，最短持有{ORIGINAL_REBOUND_MIN_HOLD}TD"
        )

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
        self.ax.set_title('创业板ETF (159915) K线图 - 周末效应 V10.02', fontsize=12)

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

        # 获取MA30数据
        ma30_value = row.get('MA30', None)
        if pd.notna(ma30_value):
            ma30_str = f"\nMA30: {ma30_value:.3f}"
        else:
            ma30_str = ""

        text = (f"{date.strftime('%Y-%m-%d')} {weekday}\n"
                f"开: {open_p:.3f}  高: {high_p:.3f}\n"
                f"低: {low_p:.3f}  收: {close_p:.3f}\n"
                f"涨跌: {change_str}{ma30_str}")

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

        latest = self.df[self.df['is_warmup'] == False].iloc[-1]
        latest_idx = latest.name

        date_str = self.realtime_price.get('date')
        try:
            today = pd.to_datetime(date_str) if date_str else datetime.now()
        except Exception:
            today = datetime.now()

        weekday = today.weekday()
        month = today.month

        price = self.realtime_price['price']
        open_price = self.realtime_price.get('open', price)
        high_price = self.realtime_price.get('high', price)
        low_price = self.realtime_price.get('low', price)
        previous_close = self.realtime_price.get('yesterday_close') or latest['收盘']

        close_ma_values = {
            'ma5': latest['MA5'],
            'ma10': latest['MA10'],
            'ma30': latest['MA30'],
        }
        strategy1_ma_values = close_ma_values.copy()

        self.date_var.set(today.strftime('%Y-%m-%d'))
        self.weekday_var.set(WEEKDAY_NAMES[weekday])
        self.price_var.set(f"{price:.3f}")

        self.ma5_var.set(f"{close_ma_values['ma5']:.3f}" if not pd.isna(close_ma_values['ma5']) else "--")
        self.ma10_var.set(f"{close_ma_values['ma10']:.3f}" if not pd.isna(close_ma_values['ma10']) else "--")
        self.ma30_var.set(f"{close_ma_values['ma30']:.3f}" if not pd.isna(close_ma_values['ma30']) else "--")

        last_week_close = self.get_last_week_close_by_index(latest_idx)
        week_decline = ((price - last_week_close) / last_week_close) if last_week_close else None

        yesterday_high = latest['最高']
        day_before_high = self.get_previous_high_by_index(latest_idx, 1)

        self.analyze_signal(
            signal_date=today,
            price=price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            previous_close=previous_close,
            close_ma_values=close_ma_values,
            strategy1_ma_values=strategy1_ma_values,
            weekday=weekday,
            month=month,
            week_decline=week_decline,
            yesterday_high=yesterday_high,
            day_before_high=day_before_high,
            close_confirmed=False,
            realtime_mode=True,
        )
        self.update_price_range(price, close_ma_values['ma30'])

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
        info_window.title("周末效应 V10.02 策略说明")
        info_window.geometry("700x600")

        text = scrolledtext.ScrolledText(info_window, font=('微软雅黑', 10), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        strategy_text = """
================================================================================
周末效应 V10.02 - 创业板ETF策略
================================================================================
标的：创业板ETF (159915)
时间：2018-01-01 至今
杠杆：2.5倍融资

【历史表现】
- 总交易: 249
- 成功率: 58.23%
- 年度独立累计净收益: 1064.14万
- 最大年度回撤: -31.60%
- 收益回撤比: 3.74

================================================================================
【策略参数】
================================================================================
- MA30阈值: 0.99 (价格需>MA30*0.99)
- MA30最大距离: 20%
- MA5最大距离: 5%
- MA10最大距离: 12%
- 排除月份: 12月
- 策略1止损: 2.5%
- 周四/周五止损: 3.5%

================================================================================
【策略1：两段式 3%/4% 回撤买入】
================================================================================
1. 参考价 R = max(昨天高点, 前天高点, 当天开盘价)
2. 若开盘 <= 4% 回撤线，则按开盘价买入
3. 否则若盘中最低 <= 4% 回撤线，则按 4% 回撤线买入
4. 否则若盘中最低 <= 3% 回撤线，且收盘 >= 3% 回撤线，则按 3% 回撤线买入
5. 以前一交易日均线 + 实际买入价检查 MA 框架
6. 持有 3 个交易日，止损 2.5%
7. 卖点优化：前3日最低点反弹8%时，盘中阈值卖，最短持有3TD

================================================================================
【周四策略】
================================================================================
1. 当日是周四
2. 非12月
3. MA条件满足
4. 本周相对上周最后交易日跌幅:
   - 2%~4%: thursday_2_4，下周二卖
   - 4%~6%: thursday_4_6，下周四卖
   - ≥6%: thursday_6plus，下周四卖

================================================================================
【周五策略】
================================================================================
1. 当日是周五
2. 非12月
3. MA条件满足
4. 子类型:
   - friday_week_down: 本周跌超3%，下周四卖
   - friday_day_down: 周五单日跌超3%，下周三卖
   - friday_strong: 周五涨超3%且本周涨超5%，下周一卖
   - friday_normal: 其他情况，下周一卖
5. 卖点优化：前1日最低点反弹5%时，盘中阈值卖，最短持有2TD
================================================================================
"""
        text.insert(tk.END, strategy_text)
        text.config(state=tk.DISABLED)
