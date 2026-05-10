#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
周末效应 V10.03 策略模块 - 创业板ETF周末效应策略
================================================================================
标的：创业板ETF (159915)
策略：
1. 保留原 v9 的周四 / 周五策略
2. 策略1升级为两段式 3%/4% 回撤买入
3. 新增“当天最高价收盘补买”分支
4. 周四 / 周五策略保持原 v9 框架
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

# ==================== 策略参数（V10.03）====================
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
        self.intraday_snapshot = None
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
        def make_signal_label(parent, textvariable, font, pady=1):
            label = ttk.Label(
                parent,
                textvariable=textvariable,
                font=font,
                justify=tk.LEFT,
                anchor='w'
            )
            label.pack(anchor=tk.W, fill=tk.X, pady=pady)

            def update_wrap(event, lbl=label):
                wrap = max(event.width - 24, 120)
                lbl.configure(wraplength=wrap)

            parent.bind("<Configure>", update_wrap, add="+")
            return label

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
        self.refresh_time_var = tk.StringVar(value="最新刷新: --")
        ttk.Label(row2, textvariable=self.refresh_time_var, font=('微软雅黑', 14), foreground='gray').pack(side=tk.RIGHT, padx=5)

        # ===== 信号区与参考买卖规则同层展示 =====
        top_sections = ttk.Frame(main_frame)
        top_sections.pack(fill=tk.X, pady=(0, 10))
        top_sections.columnconfigure(0, weight=16, minsize=420)
        top_sections.columnconfigure(1, weight=11, minsize=290)
        top_sections.columnconfigure(2, weight=11, minsize=290)
        top_sections.columnconfigure(3, weight=9, minsize=310)

        # 左列：策略1两段式买入（最高优先级）
        left_frame = ttk.LabelFrame(top_sections, text="策略1 两段式买入 (V10.03)", padding="5")
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))

        self.sup_month_var = tk.StringVar(value="月份: --")
        self.sup_month_label = make_signal_label(left_frame, self.sup_month_var, ('微软雅黑', 15))

        self.sup_ma_var = tk.StringVar(value="MA条件: --")
        self.sup_ma_label = make_signal_label(left_frame, self.sup_ma_var, ('微软雅黑', 15))

        self.sup_ref_var = tk.StringVar(value="盘中参考价/跌幅线: --")
        self.sup_ref_label = make_signal_label(left_frame, self.sup_ref_var, ('微软雅黑', 15))

        self.sup_drop_var = tk.StringVar(value="盘中触发状态: --")
        self.sup_drop_label = make_signal_label(left_frame, self.sup_drop_var, ('微软雅黑', 15))

        self.sup_entry_var = tk.StringVar(value="策略1买点: --")
        self.sup_entry_label = make_signal_label(left_frame, self.sup_entry_var, ('微软雅黑', 15))

        self.sup_result_var = tk.StringVar(value="")
        self.sup_result_label = make_signal_label(left_frame, self.sup_result_var, ('微软雅黑', 18, 'bold'), pady=(5, 0))

        # 中列：周四买入条件
        mid_frame = ttk.LabelFrame(top_sections, text="周四买入条件", padding="5")
        mid_frame.grid(row=0, column=1, sticky='nsew', padx=5)

        self.thu_weekday_var = tk.StringVar(value="星期: --")
        self.thu_weekday_label = make_signal_label(mid_frame, self.thu_weekday_var, ('微软雅黑', 15))

        self.thu_month_var = tk.StringVar(value="月份: --")
        self.thu_month_label = make_signal_label(mid_frame, self.thu_month_var, ('微软雅黑', 15))

        self.thu_ma_var = tk.StringVar(value="MA条件: --")
        self.thu_ma_label = make_signal_label(mid_frame, self.thu_ma_var, ('微软雅黑', 15))

        self.thu_decline_var = tk.StringVar(value="周涨跌幅: --")
        self.thu_decline_label = make_signal_label(mid_frame, self.thu_decline_var, ('微软雅黑', 15))

        self.thu_result_var = tk.StringVar(value="")
        self.thu_result_label = make_signal_label(mid_frame, self.thu_result_var, ('微软雅黑', 18, 'bold'), pady=(5, 0))

        # 右列：周五买入条件
        right_frame = ttk.LabelFrame(top_sections, text="周五买入条件", padding="5")
        right_frame.grid(row=0, column=2, sticky='nsew', padx=(5, 0))

        self.fri_weekday_var = tk.StringVar(value="星期: --")
        self.fri_weekday_label = make_signal_label(right_frame, self.fri_weekday_var, ('微软雅黑', 15))

        self.fri_month_var = tk.StringVar(value="月份: --")
        self.fri_month_label = make_signal_label(right_frame, self.fri_month_var, ('微软雅黑', 15))

        self.fri_ma_var = tk.StringVar(value="MA条件: --")
        self.fri_ma_label = make_signal_label(right_frame, self.fri_ma_var, ('微软雅黑', 15))

        self.fri_decline_var = tk.StringVar(value="周涨跌幅: --")
        self.fri_decline_label = make_signal_label(right_frame, self.fri_decline_var, ('微软雅黑', 15))

        self.fri_result_var = tk.StringVar(value="")
        self.fri_result_label = make_signal_label(right_frame, self.fri_result_var, ('微软雅黑', 18, 'bold'), pady=(5, 0))

        # 第四列：参考买卖规则
        price_range_frame = ttk.LabelFrame(top_sections, text="参考买卖规则", padding="10")
        price_range_frame.grid(row=0, column=3, sticky='nsew', padx=(10, 0))

        self.buy_price_range_var = tk.StringVar(value="买入区间: -- ~ --")
        self.buy_price_range_label = make_signal_label(
            price_range_frame, self.buy_price_range_var, ('微软雅黑', 15, 'bold'), pady=2
        )

        self.stop_loss_var = tk.StringVar(value="止损价(跌幅): --")
        self.stop_loss_label = make_signal_label(
            price_range_frame, self.stop_loss_var, ('微软雅黑', 14), pady=4
        )

        self.sell_rule_var = tk.StringVar(value="策略1卖出规则: --")
        self.sell_rule_label = make_signal_label(
            price_range_frame, self.sell_rule_var, ('微软雅黑', 14), pady=4
        )

        self.sell_rule2_var = tk.StringVar(value="周四/周五卖出规则: --")
        self.sell_rule2_label = make_signal_label(
            price_range_frame, self.sell_rule2_var, ('微软雅黑', 14), pady=4
        )

        # ===== K线图区：横向贯穿 =====
        chart_frame = ttk.LabelFrame(main_frame, text="K线图", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.chart_frame = chart_frame

        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        chart_widget = self.canvas.get_tk_widget()
        chart_widget.pack(fill=tk.BOTH, expand=True)
        self.chart_widget = chart_widget
        self._chart_resize_job = None
        chart_frame.bind("<Configure>", self.on_chart_resize, add="+")

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

    def on_chart_resize(self, event):
        """图表区域尺寸变化时，让 matplotlib 真正跟着容器变宽变高"""
        if event.width < 50 or event.height < 50:
            return

        if self._chart_resize_job is not None:
            try:
                self.parent.after_cancel(self._chart_resize_job)
            except Exception:
                pass

        self._chart_resize_job = self.parent.after(80, self.resize_chart_to_widget)

    def resize_chart_to_widget(self):
        """按当前 Tk 容器尺寸重设 figure 大小"""
        self._chart_resize_job = None

        if not hasattr(self, 'chart_widget') or not hasattr(self, 'chart_frame'):
            return

        self.chart_frame.update_idletasks()
        width = max(self.chart_frame.winfo_width() - 12, 50)
        height = max(self.chart_frame.winfo_height() - 36, 50)
        if width < 50 or height < 50:
            return

        self.chart_widget.configure(width=width, height=height)
        dpi = self.fig.get_dpi() or 100
        self.fig.set_size_inches(width / dpi, height / dpi, forward=True)
        self.fig.subplots_adjust(left=0.055, right=0.995, top=0.92, bottom=0.16)
        self.canvas.draw()

    def load_data(self):
        """加载K线数据"""
        self.status_var.set("正在加载数据...")
        try:
            from weekend_data_updater import is_trading_time, get_market_now

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

            now = get_market_now().strftime('%H:%M:%S')
            self.refresh_time_var.set(f"最新刷新: {now}")

            # 交易日优先抓一次实时行情，避免界面日期停留在上一根日线
            is_trading_day, _, _ = is_trading_time()
            if is_trading_day:
                self.parent.after(200, self.refresh_realtime)

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
        self.thu_weekday_label.configure(foreground='black')

        self.thu_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.thu_month_label.configure(foreground='black')

        self.thu_ma_var.set(f"{close_ma['text']}{mode_hint}")
        self.thu_ma_label.configure(foreground='black')

        # 周跌幅条件
        if week_decline is not None:
            decline_pct = week_decline * 100
            if week_decline <= -0.06:
                thu_subtype = "thursday_6plus"
                thu_decline_text = f"周涨跌幅: {decline_pct:+.2f}% (<=-6.00%，下周四卖)"
            elif week_decline <= -0.04:
                thu_subtype = "thursday_4_6"
                thu_decline_text = f"周涨跌幅: {decline_pct:+.2f}% (-6.00%~-4.00%，下周四卖)"
            elif week_decline <= -0.02:
                thu_subtype = "thursday_2_4"
                thu_decline_text = f"周涨跌幅: {decline_pct:+.2f}% (-4.00%~-2.00%，下周二卖)"
            else:
                thu_subtype = None
                thu_decline_text = f"周涨跌幅: {decline_pct:+.2f}% (未达-2.00%)"

            self.thu_decline_var.set(thu_decline_text)
            self.thu_decline_label.configure(foreground='black')
        else:
            thu_subtype = None
            self.thu_decline_var.set("周涨跌幅: 无数据")
            self.thu_decline_label.configure(foreground='black')

        thu_signal = thu_weekday_ok and month_ok and close_ma['valid'] and thu_subtype is not None
        if thu_signal:
            self.thu_result_var.set(f"✓ 满足周四买入：{thu_subtype}")
            self.thu_result_label.configure(foreground='black')
        else:
            self.thu_result_var.set("✗ 不满足")
            self.thu_result_label.configure(foreground='gray')

        # ===== 周五买入条件 =====
        fri_weekday_ok = weekday == 4
        self.fri_weekday_var.set(f"星期: {WEEKDAY_NAMES[weekday]} (需要周五)")
        self.fri_weekday_label.configure(foreground='black')

        self.fri_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.fri_month_label.configure(foreground='black')

        self.fri_ma_var.set(f"{close_ma['text']}{mode_hint}")
        self.fri_ma_label.configure(foreground='black')

        day_change = None
        if previous_close and previous_close != 0:
            day_change = (price - previous_close) / previous_close

        if week_decline is not None and day_change is not None:
            if week_decline < -0.03:
                fri_subtype = "friday_week_down"
                fri_text = f"周涨跌幅 {week_decline*100:+.2f}% (下周四卖)"
            elif day_change < -0.03:
                fri_subtype = "friday_day_down"
                fri_text = f"周五涨跌幅 {day_change*100:+.2f}% (下周三卖)"
            elif day_change > 0.03 and week_decline > 0.05:
                fri_subtype = "friday_strong"
                fri_text = f"周强势: 日涨幅 {day_change*100:+.2f}%, 周涨幅 {week_decline*100:+.2f}% (下周一卖)"
            else:
                fri_subtype = "friday_normal"
                fri_text = f"周涨跌幅 {week_decline*100:+.2f}%, 日涨跌幅 {day_change*100:+.2f}% (下周一卖)"

            self.fri_decline_var.set(fri_text)
            self.fri_decline_label.configure(foreground='black')
        else:
            fri_subtype = None
            self.fri_decline_var.set("周涨跌幅: 无数据")
            self.fri_decline_label.configure(foreground='black')

        fri_signal = fri_weekday_ok and month_ok and close_ma['valid'] and fri_subtype is not None
        if fri_signal:
            self.fri_result_var.set(f"✓ 满足周五买入：{fri_subtype}")
            self.fri_result_label.configure(foreground='black')
        else:
            self.fri_result_var.set("✗ 不满足")
            self.fri_result_label.configure(foreground='gray')

        # ===== 策略1：两段式 3%/4% 回撤 =====
        self.sup_month_var.set(f"月份: {month}月 ({'排除' if month in EXCLUDE_MONTHS else '可交易'})")
        self.sup_month_label.configure(foreground='black')

        reference_candidates = []
        if yesterday_high is not None and not pd.isna(yesterday_high):
            reference_candidates.append(("昨高", yesterday_high))
        if day_before_high is not None and not pd.isna(day_before_high):
            reference_candidates.append(("前高", day_before_high))
        if open_price is not None and not pd.isna(open_price):
            reference_candidates.append(("今开", open_price))

        if not reference_candidates:
            self.sup_ma_var.set("MA条件: 数据不足")
            self.sup_ma_label.configure(foreground='black')
            self.sup_ref_var.set("盘中参考价/跌幅线: 无数据")
            self.sup_ref_label.configure(foreground='black')
            self.sup_drop_var.set("盘中触发状态: 无法判断")
            self.sup_drop_label.configure(foreground='black')
            self.sup_entry_var.set("策略1买点: --")
            self.sup_entry_label.configure(foreground='black')
            self.sup_result_var.set("✗ 不满足")
            self.sup_result_label.configure(foreground='gray')
            return

        ref_label, reference_price = max(reference_candidates, key=lambda item: item[1])
        yesterday_high_text = "--" if yesterday_high is None or pd.isna(yesterday_high) else f"{yesterday_high:.3f}"
        day_before_high_text = "--" if day_before_high is None or pd.isna(day_before_high) else f"{day_before_high:.3f}"
        first_stage_price = reference_price * (1 - STRATEGY1_FIRST_STAGE)
        second_stage_price = reference_price * (1 - STRATEGY1_SECOND_STAGE)
        current_drawdown_pct = max(0.0, (reference_price - low_price) / reference_price * 100)
        today_high_first_stage_price = high_price * (1 - STRATEGY1_FIRST_STAGE) if high_price is not None and not pd.isna(high_price) else None
        today_high_second_stage_price = high_price * (1 - STRATEGY1_SECOND_STAGE) if high_price is not None and not pd.isna(high_price) else None

        self.sup_ref_var.set(
            f"盘中参考价: 昨高={yesterday_high_text} / 前高={day_before_high_text} / 今开={open_price:.3f}，取{ref_label}={reference_price:.3f} | -3%跌幅线={first_stage_price:.3f} | -4%跌幅线={second_stage_price:.3f}"
        )
        self.sup_ref_label.configure(foreground='black')

        strategy1_entry_price = None
        strategy1_entry_mode = None
        signed_drawdown_pct = -current_drawdown_pct
        strategy1_trigger_text = f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，未到-3%跌幅线"
        strategy1_entry_text = "策略1买点: 未到-3%跌幅线"
        strategy1_triggered = False

        if open_price <= second_stage_price:
            strategy1_entry_price = open_price
            strategy1_entry_mode = "open_gap_below_4pct"
            strategy1_trigger_text = (
                f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                f"开盘直接低于-4%跌幅线，按开盘价 {open_price:.3f}"
            )
            strategy1_entry_text = f"策略1买点: 开盘价 {open_price:.3f}"
            strategy1_triggered = True
        elif low_price <= second_stage_price:
            strategy1_entry_price = second_stage_price
            strategy1_entry_mode = "intraday_4pct"
            strategy1_trigger_text = (
                f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                f"盘中触达-4%跌幅线，按-4%跌幅线 {second_stage_price:.3f}"
            )
            strategy1_entry_text = f"策略1买点: -4%跌幅线 {second_stage_price:.3f}"
            strategy1_triggered = True
        elif low_price <= first_stage_price:
            if close_confirmed:
                if price >= first_stage_price:
                    strategy1_entry_price = first_stage_price
                    strategy1_entry_mode = "rebound_to_3pct_by_close"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                        f"收盘重新站回-3%跌幅线，按-3%跌幅线 {first_stage_price:.3f}"
                    )
                    strategy1_entry_text = f"策略1买点: -3%跌幅线 {first_stage_price:.3f}"
                    strategy1_triggered = True
                else:
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                        "跌到-3%~-4%区间，但收盘未站回-3%跌幅线"
                    )
                    strategy1_entry_text = "策略1买点: 盘中两段式未成交，继续检查收盘相对当天最高价补买"
            else:
                if price >= first_stage_price:
                    strategy1_entry_price = first_stage_price
                    strategy1_entry_mode = "rebound_to_3pct_by_close_realtime"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                        "按当前实时收盘口径，已回到-3%跌幅线之上"
                    )
                    strategy1_entry_text = f"策略1买点: 按当前实时收盘口径，可按-3%跌幅线 {first_stage_price:.3f}"
                    strategy1_triggered = True
                else:
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前最低相对参考价 {signed_drawdown_pct:+.2f}%，"
                        "已进入-3%~-4%区间，继续观察-4%跌幅线或收盘回到-3%跌幅线"
                    )
                    strategy1_entry_text = f"策略1买点: 候选-3%跌幅线 {first_stage_price:.3f} / -4%跌幅线 {second_stage_price:.3f}"

        if strategy1_entry_price is None and high_price is not None and not pd.isna(high_price):
            close_drawdown_pct = (price - high_price) / high_price * 100
            if close_confirmed:
                if price <= today_high_second_stage_price:
                    strategy1_entry_price = price
                    strategy1_entry_mode = "today_high_close_4pct"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 盘中两段式未成交；收盘相对今日最高价 {close_drawdown_pct:+.2f}%，"
                        f"达到-4%补买条件（今高={high_price:.3f}）"
                    )
                    strategy1_entry_text = f"策略1买点: 收盘价 {price:.3f}（今高-4%补买）"
                    strategy1_triggered = True
                elif price <= today_high_first_stage_price:
                    strategy1_entry_price = price
                    strategy1_entry_mode = "today_high_close_3pct"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 盘中两段式未成交；收盘相对今日最高价 {close_drawdown_pct:+.2f}%，"
                        f"达到-3%补买条件（今高={high_price:.3f}）"
                    )
                    strategy1_entry_text = f"策略1买点: 收盘价 {price:.3f}（今高-3%补买）"
                    strategy1_triggered = True
                else:
                    if "继续检查收盘相对当天最高价补买" in strategy1_entry_text:
                        strategy1_entry_text = "策略1买点: 收盘相对当天最高价也未达到-3%补买条件，今日放弃"
            else:
                if price <= today_high_second_stage_price:
                    strategy1_entry_price = price
                    strategy1_entry_mode = "today_high_close_4pct_realtime"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前相对今日最高价 {(price - high_price) / high_price * 100:+.2f}%，"
                        f"按当前实时收盘口径，已触发今高-4%补买"
                    )
                    strategy1_entry_text = f"策略1买点: 按当前实时收盘口径，可按收盘价 {price:.3f}（今高-4%补买）"
                    strategy1_triggered = True
                elif price <= today_high_first_stage_price:
                    strategy1_entry_price = price
                    strategy1_entry_mode = "today_high_close_3pct_realtime"
                    strategy1_trigger_text = (
                        f"盘中触发状态: 当前相对今日最高价 {(price - high_price) / high_price * 100:+.2f}%，"
                        f"按当前实时收盘口径，已触发今高-3%补买"
                    )
                    strategy1_entry_text = f"策略1买点: 按当前实时收盘口径，可按收盘价 {price:.3f}（今高-3%补买）"
                    strategy1_triggered = True

        strategy1_check_price = strategy1_entry_price if strategy1_entry_price is not None else price
        strategy1_ma = self._evaluate_ma_filters(
            strategy1_check_price,
            strategy1_ma_values['ma5'],
            strategy1_ma_values['ma10'],
            strategy1_ma_values['ma30'],
        )

        ma_hint = "（以前一交易日均线检查）" if not realtime_mode else "（按前一交易日均线实时估算）"
        self.sup_ma_var.set(f"{strategy1_ma['text']}{ma_hint}")
        self.sup_ma_label.configure(foreground='black')

        self.sup_drop_var.set(strategy1_trigger_text)
        self.sup_drop_label.configure(foreground='black')
        self.sup_entry_var.set(strategy1_entry_text)
        self.sup_entry_label.configure(foreground='black')

        strategy1_signal = month_ok and strategy1_ma['valid'] and strategy1_triggered
        if strategy1_signal:
            self.sup_result_var.set("✓ 满足策略1买入")
            self.sup_result_label.configure(foreground='black')
        else:
            self.sup_result_var.set("✗ 不满足")
            self.sup_result_label.configure(foreground='gray')

    def update_price_range(self, price, ma30):
        """计算并更新可开仓价格区间"""
        if pd.isna(ma30):
            self.buy_price_range_var.set("买入区间: MA30数据不足")
            self.stop_loss_var.set("止损价(跌幅): --")
            self.sell_rule_var.set("策略1卖出规则: --")
            self.sell_rule2_var.set("周四/周五卖出规则: --")
            return

        # 买入区间: MA30*0.99 ~ MA30*1.20
        buy_min = ma30 * MA30_THRESHOLD
        buy_max = ma30 * (1 + MA30_MAX_DIST)
        self.buy_price_range_var.set(f"买入区间: {buy_min:.3f} ~ {buy_max:.3f}")

        strategy1_stop = price * STRATEGY1_STOP_LOSS_RATE
        original_stop = price * ORIGINAL_STOP_LOSS_RATE
        self.stop_loss_var.set(
            f"止损价(跌幅): 策略1 {strategy1_stop:.3f} (止损跌幅 -2.5%) | "
            f"周四/周五 {original_stop:.3f} (止损跌幅 -3.5%)"
        )

        self.sell_rule_var.set(
            "策略1卖出规则: 固定持有3个交易日；若先触发止损，则按 -2.5% 止损规则卖出"
        )
        self.sell_rule2_var.set(
            "周四/周五卖出规则: 到各自计划卖出日按收盘卖出；若先触发止损，则按 -3.5% 止损规则卖出"
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
        self.ax.set_title('创业板ETF (159915) K线图 - 周末效应 V10.03', fontsize=12)

        self.fig.subplots_adjust(left=0.055, right=0.995, top=0.92, bottom=0.16)
        self.hover_annotation = None
        self.hover_vline = None
        self.resize_chart_to_widget()
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
        if self.auto_refresh_id is not None:
            try:
                self.parent.after_cancel(self.auto_refresh_id)
            except Exception:
                pass
            self.auto_refresh_id = None

        if not self.auto_refresh_enabled:
            return

        try:
            from weekend_data_updater import is_trading_time, get_market_now

            is_trading_day, is_trading_hours, _ = is_trading_time()
            market_now = get_market_now()
            current_minutes = market_now.hour * 60 + market_now.minute
            market_open_minutes = 9 * 60 + 30

            if is_trading_day and is_trading_hours and self.auto_refresh_enabled:
                self.refresh_realtime()
                self.auto_refresh_id = self.parent.after(60000, self.start_auto_refresh)
                self.realtime_var.set("自动刷新中...")
                self.realtime_label.configure(foreground='black')
            elif is_trading_day and not is_trading_hours:
                # 交易日但非连续竞价时，若已开盘过（午休/收盘后），仍先抓一次当日实时行情
                if current_minutes >= market_open_minutes:
                    self.refresh_realtime()

                if market_now.hour < 9 or (market_now.hour == 9 and market_now.minute < 30):
                    self.realtime_var.set("盘前等待")
                elif market_now.hour >= 15:
                    self.realtime_var.set("已收盘")
                else:
                    self.realtime_var.set("午休")
                self.realtime_label.configure(foreground='gray')
                if self.auto_refresh_enabled:
                    self.auto_refresh_id = self.parent.after(300000, self.start_auto_refresh)
            else:
                self.realtime_var.set("休市")
                self.realtime_label.configure(foreground='gray')
        except Exception as e:
            self.realtime_var.set("--")
            self.realtime_label.configure(foreground='gray')

    def set_active(self, active):
        """设置当前页是否为活动页，只刷新当前页。"""
        self.auto_refresh_enabled = active
        if not active:
            if self.auto_refresh_id is not None:
                try:
                    self.parent.after_cancel(self.auto_refresh_id)
                except Exception:
                    pass
                self.auto_refresh_id = None
            return
        self.start_auto_refresh()

    def _merge_intraday_snapshot(self, realtime):
        """维护当日实时开高低收快照，避免接口偶发回退高低点。"""
        from weekend_data_updater import get_market_now

        date_str = realtime.get('date')
        try:
            trade_date = pd.to_datetime(date_str).date() if date_str else get_market_now().date()
        except Exception:
            trade_date = get_market_now().date()

        price = realtime.get('price', 0) or 0
        open_price = realtime.get('open', price) or price
        high_price = realtime.get('high', price) or price
        low_price = realtime.get('low', price) or price

        if self.intraday_snapshot is None or self.intraday_snapshot.get('date') != trade_date:
            self.intraday_snapshot = {
                'date': trade_date,
                'open': open_price,
                'high': max(high_price, price, open_price),
                'low': min(low_price, price, open_price),
            }
        else:
            snap = self.intraday_snapshot
            if not snap.get('open') and open_price:
                snap['open'] = open_price
            snap['high'] = max(snap.get('high', high_price), high_price, price, snap.get('open', price))
            snap['low'] = min(snap.get('low', low_price), low_price, price, snap.get('open', price))

        merged = dict(realtime)
        merged['date'] = trade_date.strftime('%Y-%m-%d')
        merged['open'] = self.intraday_snapshot['open']
        merged['high'] = self.intraday_snapshot['high']
        merged['low'] = self.intraday_snapshot['low']
        merged['price'] = price
        return merged

    def refresh_realtime(self):
        """获取实时行情并更新显示"""
        try:
            from weekend_data_updater import get_etf_realtime_price, get_market_now

            realtime = get_etf_realtime_price()
            if realtime:
                self.realtime_price = self._merge_intraday_snapshot(realtime)
                price = self.realtime_price['price']
                time_str = self.realtime_price.get('time', '')[:5]
                source = self.realtime_price.get('source', '')

                self.realtime_var.set(f"{price:.3f} ({time_str}) [{source}]")
                self.realtime_label.configure(foreground='black')

                now = get_market_now().strftime('%H:%M:%S')
                self.refresh_time_var.set(f"最新刷新: {now}")

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
            from weekend_data_updater import get_market_now
            today = pd.to_datetime(date_str) if date_str else get_market_now()
        except Exception:
            from weekend_data_updater import get_market_now
            today = get_market_now()

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
        try:
            from weekend_data_updater import is_trading_time
            is_trading_day, _, _ = is_trading_time()
            if is_trading_day:
                self.refresh_realtime()
        except Exception:
            pass

        self.status_var.set("数据更新完成")
        messagebox.showinfo("更新结果", result)

    def on_update_error(self, error):
        """数据更新错误回调"""
        self.status_var.set("数据更新失败")
        messagebox.showerror("错误", f"数据更新失败:\n{error}")

    def show_strategy_info(self):
        """显示策略说明"""
        info_window = tk.Toplevel(self.root)
        info_window.title("周末效应 V10.03 策略说明")
        info_window.geometry("700x600")

        text = scrolledtext.ScrolledText(info_window, font=('微软雅黑', 10), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        strategy_text = """
================================================================================
周末效应 V10.03 - 创业板ETF策略
================================================================================
标的：创业板ETF (159915)
时间：2018-01-01 至今
杠杆：2.5倍融资

【历史表现】
- 总交易: 252
- 成功率: +58.73%
- 年度独立累计净收益: 1012.54万
- 最大年度回撤: -31.60%
- 收益回撤比: 3.56

================================================================================
【策略参数】
================================================================================
- MA30阈值: 0.99 (价格需>MA30*0.99)
- MA30最大距离: +20%
- MA5最大距离: +5%
- MA10最大距离: +12%
- 排除月份: 12月
- 策略1止损跌幅: -2.5%
- 周四/周五止损跌幅: -3.5%

================================================================================
【策略1：两段式 3%/4% 回撤买入 + 当天最高价收盘补买】
================================================================================
1. 参考价 R = max(昨天高点, 前天高点, 当天开盘价)
2. 若开盘 <= -4% 跌幅线，则按开盘价买入
3. 否则若盘中最低 <= -4% 跌幅线，则按 -4% 跌幅线买入
4. 否则若盘中最低 <= -3% 跌幅线，且收盘 >= -3% 跌幅线，则按 -3% 跌幅线买入
5. 若盘中两段式未成交，再检查收盘相对当天最高价：
   - 收盘 <= 当天最高价 × 0.96：按收盘价补买（今高-4%补买）
   - 否则若收盘 <= 当天最高价 × 0.97：按收盘价补买（今高-3%补买）
6. 以前一交易日均线 + 实际买入价检查 MA 框架
7. 固定持有 3 个交易日，止损跌幅 -2.5%

================================================================================
【周四策略】
================================================================================
1. 当日是周四
2. 非12月
3. MA条件满足
4. 本周相对上周最后交易日涨跌幅:
   - -4%~-2%: thursday_2_4，下周二卖
   - -6%~-4%: thursday_4_6，下周四卖
   - <= -6%: thursday_6plus，下周四卖

================================================================================
【周五策略】
================================================================================
1. 当日是周五
2. 非12月
3. MA条件满足
4. 子类型:
   - friday_week_down: 本周跌超 -3%，下周四卖
   - friday_day_down: 周五单日跌超 -3%，下周三卖
   - friday_strong: 周五涨超 +3% 且本周涨超 +5%，下周一卖
   - friday_normal: 其他情况，下周一卖
5. 周五策略本身不额外做盘中止盈，仍按原计划卖出日或止损执行

================================================================================
【卖出与止损执行】
================================================================================
1. 策略1：
   - 计划卖出：买入后第 3 个交易日收盘
   - 止损：若开盘已低于止损价，则按开盘价卖；否则若盘中最低价低于止损价，则按止损价卖
2. 周四 / 周五策略：
   - 计划卖出：按各子策略对应的目标卖出日收盘
   - 止损：若开盘已低于止损价，则按开盘价卖；否则若盘中最低价低于止损价，则按止损价卖
================================================================================
"""
        text.insert(tk.END, strategy_text)
        text.config(state=tk.DISABLED)
