#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 数据更新改进版 V2 - 纯新浪API实现，支持数据缺口自动补全
================================================================================
关键改进：
1. 获取新浪API返回的多条历史K线数据（而非仅取前一天）
2. 自动检测数据缺口
3. 智能补全缺失的交易日数据
4. 不依赖其他API，仅使用现有的新浪接口
================================================================================
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
import re

# 导入原有模块的必要函数
from data_updater import (
    get_data_path,
    get_current_quarterly_contract,
    get_realtime_price,
    is_trading_time,
    _get_current_quarterly_contract,
    get_delivery_date
)


def get_sina_historical_klines(contract, days_back=60):
    """
    从新浪获取指定合约的多条历史K线数据

    关键改进：返回多条数据（而非仅取前一天），用于补全缺口

    参数:
        contract: 合约代码 (如 'IF2603')
        days_back: 回溯天数（获取最近N条K线）

    返回: list of dict，包含 {'date', 'open', 'high', 'low', 'close', 'volume'}
    """
    try:
        url = 'https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_result=/InnerFuturesNewService.getDailyKLine'
        params = {
            'symbol': contract,
            'type': '0'  # 日K线
        }
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0'
        }

        resp = requests.get(url, params=params, headers=headers, timeout=10)
        text = resp.text

        # 解析 JSONP 响应: var _result=([...])
        start = text.find('([')
        end = text.rfind('])')
        if start == -1 or end == -1:
            return []

        data_list = json.loads(text[start+1:end+1])

        if not data_list:
            return []

        # 转换为标准格式，返回最近N条
        klines = []
        for item in data_list[-days_back:]:  # 获取最近days_back条
            kline = {
                'date': item.get('d', ''),
                'open': float(item.get('o', 0)),
                'high': float(item.get('h', 0)),
                'low': float(item.get('l', 0)),
                'close': float(item.get('c', 0)),
                'volume': int(float(item.get('v', 0))),
            }
            if kline['date']:  # 只保留有日期的数据
                klines.append(kline)

        return klines

    except Exception as e:
        print(f"获取新浪历史K线失败: {e}")
        return []


def detect_data_gaps(df):
    """
    检测DataFrame中的数据缺口（缺失的交易日）

    参数:
        df: 包含'日期'列的DataFrame

    返回: {'missing_dates': [缺失日期列表], 'gaps': [(开始日期, 结束日期, 缺失天数), ...]}
    """
    if len(df) == 0:
        return {'missing_dates': [], 'gaps': []}

    df = df.sort_values('日期').reset_index(drop=True)
    df['日期'] = pd.to_datetime(df['日期'])

    first_date = df['日期'].min()
    last_date = df['日期'].max()

    # 生成应该有的所有交易日（周一到周五）
    trading_dates = []
    current = first_date
    while current <= last_date:
        if current.weekday() < 5:  # 0=周一，4=周五
            trading_dates.append(current.date())
        current += timedelta(days=1)

    # 实际有的交易日
    actual_dates = set(df['日期'].dt.date)
    expected_dates = set(trading_dates)

    # 缺失的交易日
    missing_dates = sorted(expected_dates - actual_dates)

    # 分析缺口模式（连续的缺失日期分组）
    gaps = []
    if missing_dates:
        gap_start = missing_dates[0]
        gap_end = missing_dates[0]

        for i in range(1, len(missing_dates)):
            if (missing_dates[i] - missing_dates[i-1]).days == 1:
                gap_end = missing_dates[i]
            else:
                gaps.append((gap_start, gap_end, (gap_end - gap_start).days + 1))
                gap_start = missing_dates[i]
                gap_end = missing_dates[i]

        gaps.append((gap_start, gap_end, (gap_end - gap_start).days + 1))

    return {
        'missing_dates': [pd.Timestamp(d) for d in missing_dates],
        'gaps': gaps,
        'total_missing': len(missing_dates)
    }


def fill_data_gaps_sina(df, gap_info, contract):
    """
    使用新浪API补全数据缺口

    参数:
        df: 原始DataFrame
        gap_info: detect_data_gaps()的返回值
        contract: 合约代码

    返回: 补全后的DataFrame
    """
    missing_dates = gap_info['missing_dates']

    if not missing_dates or len(missing_dates) == 0:
        return df

    print(f"\n【使用新浪API补全{len(missing_dates)}条缺失数据】")

    # 获取足够长的历史数据（从最早的缺口开始往前多取些）
    earliest_missing = missing_dates[0]
    days_to_fetch = (df['日期'].max() - earliest_missing).days + 30  # 多取30天以确保覆盖

    print(f"正在从新浪获取最近{days_to_fetch}天的历史K线...")

    klines = get_sina_historical_klines(contract, days_back=days_to_fetch)

    if not klines:
        print("✗ 新浪API未返回数据")
        return df

    print(f"✓ 获取到{len(klines)}条K线数据")

    # 转换为DataFrame
    df_klines = pd.DataFrame(klines)
    df_klines['日期'] = pd.to_datetime(df_klines['date'])
    df_klines = df_klines[['日期', 'open', 'high', 'low', 'close', 'volume']]
    df_klines.columns = ['日期', '开盘', '最高', '最低', '收盘', '成交量']

    # 添加合约列
    df_klines['合约'] = contract
    df_klines['持仓量'] = 0  # 新浪日K线不提供持仓量

    # 标准化列顺序
    required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '持仓量', '合约']
    df_klines = df_klines[required_cols]

    # 只保留缺失日期范围内的数据
    missing_dates_set = set([d.date() for d in missing_dates])
    df_fill = df_klines[df_klines['日期'].dt.date.isin(missing_dates_set)]

    if len(df_fill) > 0:
        print(f"成功补全{len(df_fill)}条缺失数据: {df_fill['日期'].min().strftime('%Y-%m-%d')} ~ {df_fill['日期'].max().strftime('%Y-%m-%d')}")

        # 合并数据（新数据覆盖旧数据）
        df_result = pd.concat([df, df_fill], ignore_index=True)
        df_result = df_result.drop_duplicates(subset=['日期'], keep='last')
        df_result = df_result.sort_values('日期').reset_index(drop=True)

        return df_result
    else:
        print("⚠ 新浪API返回的数据不在缺失范围内")
        return df


def update_if_data_with_auto_fill():
    """
    改进的数据更新函数 - 自动检测和补全数据缺口（纯新浪API）
    """
    from data_updater import update_from_main_contract

    print("="*70)
    print("IF300 数据更新 - 改进版V2（自动缺口补全，纯新浪API）")
    print("="*70)

    # 第一步：执行常规更新
    print("\n【第一步】执行常规数据更新（实时价格 + 前一交易日）...")
    try:
        result = update_from_main_contract()
        print(result)
    except Exception as e:
        print(f"✗ 常规更新失败: {e}")
        return

    # 第二步：检测数据缺口
    print("\n【第二步】检测数据缺口...")

    data_path = get_data_path()
    file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

    if not os.path.exists(file_path):
        print("✗ 数据文件不存在")
        return

    df = pd.read_csv(file_path)
    df['日期'] = pd.to_datetime(df['日期'])

    gap_info = detect_data_gaps(df)

    if gap_info['total_missing'] == 0:
        print(f"✓ 无数据缺口")
        print(f"  最新日期: {df['日期'].max().strftime('%Y-%m-%d')}")
        return

    print(f"✗ 发现{gap_info['total_missing']}条缺失数据（交易日）")
    for gap_start, gap_end, count in gap_info['gaps']:
        print(f"  缺口: {gap_start} ~ {gap_end} ({count}天)")

    # 第三步：补全缺口
    print("\n【第三步】自动补全数据缺口（使用新浪API）...")

    contract = get_current_quarterly_contract()
    df_filled = fill_data_gaps_sina(df, gap_info, contract)

    # 第四步：保存更新后的数据
    df_filled.to_csv(file_path, index=False, encoding='utf-8-sig')

    # 第五步：验证补全效果
    print("\n【第四步】验证补全结果...")

    gap_info_after = detect_data_gaps(df_filled)

    if gap_info_after['total_missing'] == 0:
        print("✓ 数据缺口已全部补全！")
        print(f"  数据范围: {df_filled['日期'].min().strftime('%Y-%m-%d')} ~ {df_filled['日期'].max().strftime('%Y-%m-%d')}")
        print(f"  总记录数: {len(df_filled)}")
    else:
        print(f"⚠ 仍有{gap_info_after['total_missing']}条数据未补全")
        print("  原因：新浪API返回的数据可能不够长")
        for gap_start, gap_end, count in gap_info_after['gaps']:
            print(f"    未补: {gap_start} ~ {gap_end}")

    print("\n" + "="*70)


def main():
    """主函数"""
    update_if_data_with_auto_fill()


if __name__ == '__main__':
    main()
