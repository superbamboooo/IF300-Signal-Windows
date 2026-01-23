#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
周末效应策略 - 数据更新模块
================================================================================
功能：
1. 获取159915创业板ETF实时行情（多数据源备份）
2. 更新历史K线数据
3. 交易时间判断
================================================================================
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta


def is_trading_time():
    """
    判断当前是否在交易时段内
    A股/ETF交易时间：
    - 上午：9:30 - 11:30
    - 下午：13:00 - 15:00
    返回: (is_trading_day, is_trading_hours, time_hint)
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=周一, 6=周日
    hour = now.hour
    minute = now.minute
    current_time = hour * 60 + minute  # 转为分钟数便于比较

    # 周末不是交易日
    if weekday >= 5:
        return False, False, "周末休市"

    # 交易时段（以分钟计）
    morning_start = 9 * 60 + 30   # 9:30
    morning_end = 11 * 60 + 30    # 11:30
    afternoon_start = 13 * 60     # 13:00
    afternoon_end = 15 * 60       # 15:00

    # 判断是否在交易时段
    in_morning = morning_start <= current_time <= morning_end
    in_afternoon = afternoon_start <= current_time <= afternoon_end

    if in_morning or in_afternoon:
        return True, True, "交易时段中，日线数据将在收盘后(15:00)更新"
    elif current_time < morning_start:
        return True, False, "盘前，日线数据通常在收盘后(15:00)更新"
    elif morning_end < current_time < afternoon_start:
        return True, False, "午间休市，日线数据将在收盘后(15:00)更新"
    elif current_time > afternoon_end:
        return True, False, "已收盘，如数据未更新请稍后重试"

    return True, False, ""


def _get_realtime_sina():
    """新浪ETF实时行情接口"""
    try:
        url = 'https://hq.sinajs.cn/list=sz159915'
        headers = {'Referer': 'https://finance.sina.com.cn'}
        resp = requests.get(url, headers=headers, timeout=5)

        text = resp.text
        if '=""' in text or not text.strip():
            return None

        start = text.find('"') + 1
        end = text.rfind('"')
        if start >= end:
            return None

        data = text[start:end].split(',')
        if len(data) < 30:
            return None

        # 新浪股票数据格式
        # 0:名称, 1:今开, 2:昨收, 3:现价, 4:最高, 5:最低, 6:买一价, 7:卖一价
        # 8:成交量, 9:成交额, ...30:日期, 31:时间
        return {
            'name': data[0],
            'open': float(data[1]) if data[1] else 0,
            'yesterday_close': float(data[2]) if data[2] else 0,
            'price': float(data[3]) if data[3] else 0,
            'high': float(data[4]) if data[4] else 0,
            'low': float(data[5]) if data[5] else 0,
            'volume': int(float(data[8])) if data[8] else 0,
            'amount': float(data[9]) if data[9] else 0,
            'date': data[30] if len(data) > 30 else datetime.now().strftime('%Y-%m-%d'),
            'time': data[31] if len(data) > 31 else datetime.now().strftime('%H:%M:%S'),
            'source': '新浪'
        }
    except Exception as e:
        print(f"新浪ETF接口失败: {e}")
        return None


def _get_realtime_tencent():
    """腾讯ETF实时行情接口"""
    try:
        url = 'https://qt.gtimg.cn/q=sz159915'
        resp = requests.get(url, timeout=5)

        text = resp.text
        if '=""' in text or not text.strip() or 'v_' not in text:
            return None

        start = text.find('"') + 1
        end = text.rfind('"')
        if start >= end:
            return None

        data = text[start:end].split('~')
        if len(data) < 40:
            return None

        # 腾讯数据格式
        # 1:名称, 3:现价, 4:昨收, 5:今开, 6:成交量, 7:外盘, 8:内盘
        # 9:买一价, ...33:最高, 34:最低, ...
        now = datetime.now()
        return {
            'name': data[1] if len(data) > 1 else '',
            'price': float(data[3]) if len(data) > 3 and data[3] else 0,
            'yesterday_close': float(data[4]) if len(data) > 4 and data[4] else 0,
            'open': float(data[5]) if len(data) > 5 and data[5] else 0,
            'volume': int(float(data[6]) * 100) if len(data) > 6 and data[6] else 0,
            'high': float(data[33]) if len(data) > 33 and data[33] else 0,
            'low': float(data[34]) if len(data) > 34 and data[34] else 0,
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'source': '腾讯'
        }
    except Exception as e:
        print(f"腾讯ETF接口失败: {e}")
        return None


def _get_realtime_eastmoney():
    """东方财富ETF实时行情接口"""
    try:
        url = 'https://push2.eastmoney.com/api/qt/stock/get'
        params = {
            'secid': '0.159915',
            'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
        }
        resp = requests.get(url, params=params, timeout=5)
        result = resp.json()

        if result.get('data'):
            d = result['data']
            now = datetime.now()
            # 东方财富返回的价格需要除以1000
            return {
                'name': d.get('f58', ''),
                'price': d.get('f43', 0) / 1000 if d.get('f43') else 0,
                'high': d.get('f44', 0) / 1000 if d.get('f44') else 0,
                'low': d.get('f45', 0) / 1000 if d.get('f45') else 0,
                'open': d.get('f46', 0) / 1000 if d.get('f46') else 0,
                'volume': d.get('f47', 0),
                'amount': d.get('f48', 0),
                'yesterday_close': d.get('f60', 0) / 1000 if d.get('f60') else 0,
                'date': now.strftime('%Y-%m-%d'),
                'time': now.strftime('%H:%M:%S'),
                'source': '东方财富'
            }
        return None
    except Exception as e:
        print(f"东方财富ETF接口失败: {e}")
        return None


def _get_realtime_netease():
    """网易ETF实时行情接口（备用）"""
    try:
        url = f'http://api.money.126.net/data/feed/1159915,money.api'
        resp = requests.get(url, timeout=5)

        text = resp.text
        # 网易返回格式: _ntes_quote_callback({...});
        start = text.find('(') + 1
        end = text.rfind(')')
        if start >= end:
            return None

        import json
        data = json.loads(text[start:end])
        if '1159915' in data:
            d = data['1159915']
            now = datetime.now()
            return {
                'name': d.get('name', ''),
                'price': float(d.get('price', 0)),
                'high': float(d.get('high', 0)),
                'low': float(d.get('low', 0)),
                'open': float(d.get('open', 0)),
                'volume': int(d.get('volume', 0)),
                'yesterday_close': float(d.get('yestclose', 0)),
                'date': now.strftime('%Y-%m-%d'),
                'time': d.get('time', now.strftime('%H:%M:%S')),
                'source': '网易'
            }
        return None
    except Exception as e:
        print(f"网易ETF接口失败: {e}")
        return None


def get_etf_realtime_price():
    """
    获取159915创业板ETF实时行情（带多个备用接口）
    返回: dict with keys: price, open, high, low, date, time, yesterday_close, source
          或 None（如果所有接口都失败）
    """
    # 接口优先级列表（按稳定性排序）
    providers = [
        ('新浪', _get_realtime_sina),
        ('腾讯', _get_realtime_tencent),
        ('东方财富', _get_realtime_eastmoney),
        ('网易', _get_realtime_netease),
    ]

    for name, func in providers:
        try:
            result = func()
            if result and result.get('price', 0) > 0:
                return result
        except Exception as e:
            print(f"{name}接口异常: {e}")
            continue

    print("所有ETF实时行情接口均失败")
    return None


def get_data_path():
    """获取数据目录路径"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    data_path = os.path.join(os.path.dirname(base_path), 'data')
    if not os.path.exists(data_path):
        data_path = os.path.join(base_path, 'data')
        if not os.path.exists(data_path):
            os.makedirs(data_path)
    return data_path


def update_etf_data():
    """
    更新159915 ETF数据
    优先使用东方财富API（稳定，无需额外依赖）
    """
    # 打包环境或优先使用东方财富API
    if getattr(sys, 'frozen', False):
        # 打包环境直接使用东方财富
        return update_from_eastmoney()

    # 开发环境可以尝试akshare
    try:
        import akshare as ak

        print("正在从akshare获取159915创业板ETF数据...")

        data_path = get_data_path()
        file_path = os.path.join(data_path, '159915_创业板ETF_day.csv')

        # 读取现有数据
        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path, encoding='utf-8-sig')
            df_old['日期'] = pd.to_datetime(df_old['日期'])
            last_date = df_old['日期'].max()
            print(f"现有数据最新日期: {last_date.strftime('%Y-%m-%d')}")
        else:
            df_old = None
            last_date = datetime(2015, 1, 1)

        # 获取ETF日线数据
        try:
            # 使用akshare获取ETF日线数据
            df_new = ak.fund_etf_hist_sina(symbol='sz159915')

            if df_new is not None and len(df_new) > 0:
                # 重命名列以匹配现有格式
                df_new = df_new.rename(columns={
                    'date': '日期',
                    'open': '开盘',
                    'high': '最高',
                    'low': '最低',
                    'close': '收盘',
                    'volume': '成交量'
                })
                df_new['日期'] = pd.to_datetime(df_new['日期'])

                # 只保留比现有数据更新的记录
                if df_old is not None:
                    df_new = df_new[df_new['日期'] > last_date]

                if len(df_new) > 0:
                    print(f"获取到 {len(df_new)} 条新数据")

                    # 合并数据
                    required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量']

                    if df_old is not None:
                        df_old = df_old[[c for c in required_cols if c in df_old.columns]]

                    df_new = df_new[[c for c in required_cols if c in df_new.columns]]

                    if df_old is not None:
                        df = pd.concat([df_old, df_new], ignore_index=True)
                    else:
                        df = df_new

                    df = df.drop_duplicates(subset=['日期'], keep='last')
                    df = df.sort_values('日期').reset_index(drop=True)

                    df.to_csv(file_path, index=False, encoding='utf-8-sig')

                    return f"数据更新成功，共{len(df)}条记录，最新日期: {df['日期'].max().strftime('%Y-%m-%d')}"
                else:
                    # 检查是否在交易时段
                    is_trading_day, is_trading_hours, time_hint = is_trading_time()
                    today = datetime.now().date()

                    if is_trading_day and last_date.date() < today:
                        return f"数据最新日期: {last_date.strftime('%Y-%m-%d')}\n{time_hint}"
                    else:
                        return f"数据已是最新，最新日期: {last_date.strftime('%Y-%m-%d')}"
            else:
                return "未获取到新数据"

        except Exception as e:
            print(f"akshare获取ETF数据失败: {e}")
            # 尝试备用方法
            return update_from_eastmoney()

    except ImportError:
        # akshare未安装，使用东方财富
        return update_from_eastmoney()
    except Exception as e:
        # akshare出错，使用东方财富
        print(f"akshare异常: {e}，切换到东方财富")
        return update_from_eastmoney()


def update_from_eastmoney():
    """从东方财富获取ETF数据（备用方案）"""
    try:
        print("尝试从东方财富获取数据...")

        data_path = get_data_path()
        file_path = os.path.join(data_path, '159915_创业板ETF_day.csv')

        # 东方财富日线数据API
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': '0.159915',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57',
            'klt': '101',  # 日线
            'fqt': '0',    # 不复权
            'beg': '20150101',
            'end': '20500101',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'smplmt': '5000',
            'lmt': '5000'
        }

        resp = requests.get(url, params=params, timeout=30)
        result = resp.json()

        if result.get('data') and result['data'].get('klines'):
            klines = result['data']['klines']
            rows = []
            for line in klines:
                parts = line.split(',')
                if len(parts) >= 6:
                    rows.append({
                        '日期': parts[0],
                        '开盘': float(parts[1]),
                        '收盘': float(parts[2]),
                        '最高': float(parts[3]),
                        '最低': float(parts[4]),
                        '成交量': int(parts[5])
                    })

            df = pd.DataFrame(rows)
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)

            # 与现有数据合并
            if os.path.exists(file_path):
                df_old = pd.read_csv(file_path, encoding='utf-8-sig')
                df_old['日期'] = pd.to_datetime(df_old['日期'])

                required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量']
                df_old = df_old[[c for c in required_cols if c in df_old.columns]]

                df = pd.concat([df_old, df], ignore_index=True)
                df = df.drop_duplicates(subset=['日期'], keep='last')
                df = df.sort_values('日期').reset_index(drop=True)

            # 如果是交易日，尝试获取今天的实时数据
            today = datetime.now().date()
            latest_date = df['日期'].max().date()

            if latest_date < today:
                is_trade_day, is_trade_hours, _ = is_trading_time()
                if is_trade_day:
                    realtime = get_etf_realtime_price()
                    if realtime and realtime.get('price', 0) > 0:
                        today_row = {
                            '日期': pd.Timestamp(today),
                            '开盘': realtime.get('open', realtime['price']),
                            '最高': realtime.get('high', realtime['price']),
                            '最低': realtime.get('low', realtime['price']),
                            '收盘': realtime['price'],
                            '成交量': realtime.get('volume', 0)
                        }
                        df = pd.concat([df, pd.DataFrame([today_row])], ignore_index=True)
                        df = df.sort_values('日期').reset_index(drop=True)
                        print(f"已添加今日实时数据: {realtime['price']}")

            df.to_csv(file_path, index=False, encoding='utf-8-sig')

            return f"数据更新成功（东方财富），共{len(df)}条记录，最新日期: {df['日期'].max().strftime('%Y-%m-%d')}"

        raise Exception("未获取到有效数据")

    except Exception as e:
        raise Exception(f"东方财富数据更新失败: {str(e)}")


def check_data_status():
    """检查数据状态"""
    data_path = get_data_path()
    file_path = os.path.join(data_path, '159915_创业板ETF_day.csv')

    if not os.path.exists(file_path):
        return {
            'exists': False,
            'message': '数据文件不存在'
        }

    df = pd.read_csv(file_path, encoding='utf-8-sig')
    df['日期'] = pd.to_datetime(df['日期'])

    latest_date = df['日期'].max()
    today = datetime.now().date()
    days_behind = (today - latest_date.date()).days

    return {
        'exists': True,
        'records': len(df),
        'start_date': df['日期'].min().strftime('%Y-%m-%d'),
        'end_date': latest_date.strftime('%Y-%m-%d'),
        'days_behind': days_behind,
        'needs_update': days_behind > 1,
        'message': f"数据共{len(df)}条，最新: {latest_date.strftime('%Y-%m-%d')}，落后{days_behind}天"
    }


if __name__ == '__main__':
    print("检查数据状态...")
    status = check_data_status()
    print(status['message'])

    print("\n测试实时行情接口...")
    realtime = get_etf_realtime_price()
    if realtime:
        print(f"实时价格: {realtime['price']:.3f}")
        print(f"数据来源: {realtime['source']}")
        print(f"时间: {realtime['date']} {realtime['time']}")
    else:
        print("获取实时行情失败")

    if status.get('needs_update', True):
        print("\n尝试更新数据...")
        try:
            result = update_etf_data()
            print(result)
        except Exception as e:
            print(f"更新失败: {e}")
