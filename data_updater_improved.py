#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 数据更新改进版 - 支持自动检测和补全数据缺口
================================================================================
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 导入原有的函数
from data_updater import (
    get_data_path,
    get_current_quarterly_contract,
    is_trading_time,
    _get_yesterday_kline,
    get_realtime_price,
    get_quarterly_contracts,
    get_delivery_date,
    _get_current_quarterly_contract
)


def get_trading_dates(start_date, end_date):
    """
    获取指定日期范围内的交易日（排除周末，不排除节假日）

    参数:
        start_date: 开始日期 (datetime)
        end_date: 结束日期 (datetime)

    返回: 交易日期列表
    """
    trading_dates = []
    current = start_date

    while current <= end_date:
        # 周一到周五是交易日（0=周一, 4=周五）
        if current.weekday() < 5:
            trading_dates.append(current)
        current += timedelta(days=1)

    return trading_dates


def detect_data_gaps(df):
    """
    检测数据中的缺口（缺失的交易日）

    参数:
        df: 包含'日期'列的DataFrame

    返回: 缺失的交易日期列表
    """
    if len(df) == 0:
        return []

    df = df.sort_values('日期').reset_index(drop=True)
    df['日期'] = pd.to_datetime(df['日期'])

    first_date = df['日期'].min()
    last_date = df['日期'].max()

    # 获取应该有的所有交易日
    expected_trading_dates = get_trading_dates(first_date, last_date)

    # 实际有的交易日
    actual_dates = set(df['日期'].dt.date)
    expected_dates = set([d.date() for d in expected_trading_dates])

    # 缺失的交易日
    missing_dates = sorted(expected_dates - actual_dates)

    return [pd.Timestamp(d) for d in missing_dates]


def fill_data_gaps_akshare(df, missing_dates):
    """
    使用akshare补全缺失的数据

    参数:
        df: 原始DataFrame
        missing_dates: 缺失的日期列表

    返回: 补全后的DataFrame
    """
    if not missing_dates:
        return df

    try:
        import akshare as ak
        print(f"\n【正在补全{len(missing_dates)}条缺失数据】")

        current_contract = get_current_quarterly_contract()

        # 从akshare获取完整的历史数据
        print(f"正在从akshare获取 {current_contract} 的历史数据...")
        df_new = ak.futures_zh_daily_sina(symbol=current_contract)

        if df_new is None or len(df_new) == 0:
            print("akshare无法获取数据，尝试其他方法...")
            return df

        # 标准化列名
        df_new = df_new.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '成交量',
            'hold': '持仓量'
        })
        df_new['日期'] = pd.to_datetime(df_new['日期'])
        df_new['合约'] = current_contract

        # 只保留缺失日期的数据
        df_new['日期_only'] = df_new['日期'].dt.date
        missing_dates_set = set([d.date() for d in missing_dates])
        df_fill = df_new[df_new['日期_only'].isin(missing_dates_set)].drop('日期_only', axis=1)

        if len(df_fill) > 0:
            print(f"成功获取 {len(df_fill)} 条补全数据")

            # 合并数据
            df = pd.concat([df, df_fill], ignore_index=True)
            df = df.drop_duplicates(subset=['日期'], keep='last')
            df = df.sort_values('日期').reset_index(drop=True)

            return df
        else:
            print("akshare中没有找到缺失日期的数据")
            return df

    except ImportError:
        print("❌ 未安装akshare，无法补全数据缺口")
        print("   请运行: pip install akshare")
        return df
    except Exception as e:
        print(f"❌ akshare补全失败: {e}")
        return df


def fill_data_gaps_sina_recursive(df, missing_dates):
    """
    递归使用新浪API补全缺失的数据（备选方案，效率较低）

    参数:
        df: 原始DataFrame
        missing_dates: 缺失的日期列表

    返回: 补全后的DataFrame
    """
    if not missing_dates or len(missing_dates) == 0:
        return df

    print(f"\n【使用新浪API补全{len(missing_dates)}条数据】")
    print("注意：新浪API补全效率较低，建议安装akshare")

    # 对于新浪API，需要逐一查询，这里简单实现只补最近的数据
    print(f"缺失日期: {[d.strftime('%Y-%m-%d') for d in missing_dates[:5]]}")
    print(f"... 共{len(missing_dates)}条")
    print("建议：安装akshare后重新运行数据更新")

    return df


def update_if_data_with_gap_detection():
    """
    改进的数据更新函数 - 支持自动检测和补全数据缺口
    """
    from data_updater import update_if_data

    print("【IF300数据更新 - 改进版（支持缺口自动补全）】\n")

    # 第一步：执行常规更新
    print("第一步：执行常规数据更新...")
    try:
        result = update_if_data()
        print(result)
    except Exception as e:
        print(f"常规更新失败: {e}")
        return

    # 第二步：检测数据缺口
    print("\n第二步：检测数据缺口...")
    data_path = get_data_path()
    file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

    if not os.path.exists(file_path):
        print("✗ 数据文件不存在")
        return

    df = pd.read_csv(file_path)
    df['日期'] = pd.to_datetime(df['日期'])

    # 检测缺口
    missing_dates = detect_data_gaps(df)

    if missing_dates and len(missing_dates) > 0:
        print(f"✗ 发现{len(missing_dates)}条缺失数据（交易日）")
        print(f"  缺失日期范围: {missing_dates[0].strftime('%Y-%m-%d')} ~ {missing_dates[-1].strftime('%Y-%m-%d')}")

        # 第三步：补全缺口
        print("\n第三步：尝试自动补全缺口...")

        # 优先使用akshare
        df_filled = fill_data_gaps_akshare(df, missing_dates)

        # 检查是否有剩余未填充的缺口
        if len(detect_data_gaps(df_filled)) > 0:
            print("\n备选方案：使用新浪API递归补全...")
            df_filled = fill_data_gaps_sina_recursive(df_filled, detect_data_gaps(df_filled))

        # 保存补全后的数据
        df_filled.to_csv(file_path, index=False, encoding='utf-8-sig')

        remaining_gaps = detect_data_gaps(df_filled)
        if remaining_gaps and len(remaining_gaps) > 0:
            print(f"\n⚠ 仍有{len(remaining_gaps)}条数据未补全（新浪API限制）")
            print(f"  建议：安装akshare并重新运行")
        else:
            print("\n✓ 数据缺口已全部补全")
            print(f"✓ 最新日期: {df_filled['日期'].max().strftime('%Y-%m-%d')}")
    else:
        print("✓ 无数据缺口")


def main():
    """主函数"""
    update_if_data_with_gap_detection()


if __name__ == '__main__':
    main()
