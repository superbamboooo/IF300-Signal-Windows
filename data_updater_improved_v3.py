#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IF300 数据更新改进版 V3 - 从前一天开始重新更新，确保数据完整性
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


def update_if_data_with_rollback():
    """
    改进的数据更新函数 - 从前一个交易日开始重新更新，确保数据完整性

    这样做的好处：
    1. 确保最后一个交易日的数据是完整的OHLCV，而不是盘中数据
    2. 自动检测并修正前一日的数据
    3. 避免盘中数据影响
    """
    print("="*70)
    print("IF300 数据更新 - 改进版V3（从前一日开始重新更新，确保数据完整）")
    print("="*70)

    # 第一步：读取现有数据
    print("\n【第一步】读取现有数据...")

    data_path = get_data_path()
    file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

    if not os.path.exists(file_path):
        print("✗ 数据文件不存在")
        return

    df = pd.read_csv(file_path)
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期').reset_index(drop=True)

    last_date = df['日期'].max()
    print(f"✓ 数据最后日期：{last_date.strftime('%Y-%m-%d')}")
    print(f"✓ 总记录数：{len(df)}")

    # 第二步：获取回溯日期（从前一个交易日开始）
    print("\n【第二步】确定更新起点...")

    # 获取前一个交易日（往前推，跳过周末）
    rollback_date = last_date
    for i in range(1, 10):
        check_date = last_date - timedelta(days=i)
        if check_date.weekday() < 5:  # 周一到周五
            rollback_date = check_date
            break

    print(f"最后数据日期：{last_date.strftime('%Y-%m-%d')}（{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][last_date.weekday()]}）")
    print(f"更新起点日期：{rollback_date.strftime('%Y-%m-%d')}（{['周一', '周二', '周三', '周四', '周五', '周六', '周日'][rollback_date.weekday()]}）")
    print(f"将重新更新这 {(last_date - rollback_date).days + 1} 天的数据")

    # 第三步：获取最新的K线数据
    print("\n【第三步】从新浪API获取最新K线数据...")

    contract = get_current_quarterly_contract()
    print(f"当前合约：{contract}")

    klines = get_sina_historical_klines(contract, days_back=30)

    if not klines:
        print("✗ 无法获取K线数据")
        return

    print(f"✓ 获取到 {len(klines)} 条K线数据")

    # 第四步：替换/补充数据
    print("\n【第四步】更新数据...")

    # 删除从rollback_date开始的所有数据
    df = df[df['日期'] < rollback_date].copy()
    print(f"删除了从 {rollback_date.strftime('%Y-%m-%d')} 开始的数据")
    print(f"保留 {len(df)} 条历史数据")

    # 将新K线数据转换为DataFrame格式并添加
    new_records = []
    for kline in klines:
        date = pd.to_datetime(kline['date'])
        # 只添加rollback_date之后的数据
        if date >= rollback_date:
            new_records.append({
                '日期': date,
                '开盘': kline['open'],
                '最高': kline['high'],
                '最低': kline['low'],
                '收盘': kline['close'],
                '成交量': kline['volume'],
                '持仓量': 0,  # 新浪日K线不提供持仓量
                '合约': contract
            })

    if new_records:
        df_new = pd.DataFrame(new_records)
        df = pd.concat([df, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=['日期'], keep='last')
        df = df.sort_values('日期').reset_index(drop=True)
        print(f"✓ 添加/更新了 {len(new_records)} 条新数据")
    else:
        print("⚠ 新K线数据中没有符合条件的记录")

    # 第五步：保存数据
    print("\n【第五步】保存数据...")

    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"✓ 数据已保存")
    print(f"  新的最后日期：{df['日期'].max().strftime('%Y-%m-%d')}")
    print(f"  总记录数：{len(df)}")

    print("\n" + "="*70)
    print("✅ 数据更新完成！")
    print("="*70)


def main():
    """主函数"""
    update_if_data_with_rollback()


if __name__ == '__main__':
    main()
