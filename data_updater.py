#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 季月合约数据更新模块
================================================================================
功能：
1. 从网络获取最新的IF季月合约K线数据
2. 更新本地CSV文件（季月合约连接）
3. 支持增量更新
================================================================================
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from path_manager import get_data_path


MARKET_TZ = ZoneInfo('Asia/Shanghai')


def get_market_now():
    """获取中国市场当前时间（上海时区）。"""
    return datetime.now(MARKET_TZ)


def _get_current_quarterly_contract():
    """获取当前季月合约代码"""
    now = get_market_now()
    year = now.year
    month = now.month
    day = now.day
    quarterly_months = [3, 6, 9, 12]

    # 找当前或下一个季月
    for qm in quarterly_months:
        if qm > month:
            return f"IF{year % 100:02d}{qm:02d}"
        elif qm == month:
            # 当月需要判断是否已过交割日（第三个周五）
            # 简化处理：如果是季月且日期>20，使用下一个季月
            if day > 20:
                idx = quarterly_months.index(qm)
                if idx < 3:
                    return f"IF{year % 100:02d}{quarterly_months[idx+1]:02d}"
                else:
                    return f"IF{(year + 1) % 100:02d}03"
            else:
                return f"IF{year % 100:02d}{qm:02d}"

    # 如果当年季月都过了，使用下一年3月
    return f"IF{(year + 1) % 100:02d}03"


def _get_realtime_sina():
    """新浪期货实时行情接口 - 获取季月合约"""
    try:
        contract = _get_current_quarterly_contract()
        url = f'https://hq.sinajs.cn/list=nf_{contract}'
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
        if len(data) < 20:
            return None

        now = get_market_now()

        # 获取日期，但不使用当前日期作为回退
        # 如果API没有返回日期，返回None而不是用当前日期
        date_str = data[36] if len(data) > 36 and data[36] else None
        if not date_str:
            print(f"⚠️ 新浪API未返回日期信息，数据可能不可靠")
            return None

        return {
            'open': float(data[0]) if data[0] else 0,
            'high': float(data[1]) if data[1] else 0,
            'low': float(data[2]) if data[2] else 0,
            'price': float(data[3]) if data[3] else 0,
            'volume': int(float(data[4])) if data[4] else 0,
            'hold': float(data[6]) if len(data) > 6 and data[6] else 0,
            'yesterday_close': float(data[13]) if len(data) > 13 and data[13] else 0,
            'date': date_str,
            'time': data[37] if len(data) > 37 and data[37] else now.strftime('%H:%M:%S'),
            'source': f'新浪({contract})',
            'contract': contract
        }
    except Exception as e:
        print(f"新浪接口失败: {e}")
        return None


def _get_realtime_eastmoney():
    """东方财富期货实时行情接口 - 获取季月合约"""
    try:
        contract = _get_current_quarterly_contract()
        # 东方财富期货实时行情API
        url = 'https://futsseapi.eastmoney.com/api/qt/slist/get'
        params = {
            'fid': 'f3',
            'po': '1',
            'pz': '50',
            'pn': '1',
            'np': '1',
            'spt': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fields': 'f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18',
            'secids': f'8.{contract}'  # 季月合约
        }
        resp = requests.get(url, params=params, timeout=3)
        result = resp.json()

        if result.get('data') and result['data'].get('diff'):
            items = result['data']['diff']
            if items:
                d = items[0] if isinstance(items, list) else items
                now = get_market_now()
                return {
                    'open': d.get('f17', 0),
                    'high': d.get('f15', 0),
                    'low': d.get('f16', 0),
                    'price': d.get('f2', 0),
                    'volume': d.get('f5', 0),
                    'hold': d.get('f6', 0),
                    'yesterday_close': d.get('f18', 0),
                    'date': now.strftime('%Y-%m-%d'),
                    'time': now.strftime('%H:%M:%S'),
                    'source': f'东方财富({contract})',
                    'contract': contract
                }
        return None
    except Exception as e:
        print(f"东方财富接口失败: {e}")
        return None


def _get_realtime_hexun():
    """和讯期货实时行情接口 - 获取季月合约"""
    try:
        contract = _get_current_quarterly_contract()
        # 和讯期货实时数据
        url = 'http://webftcn.hermes.hexun.com/shf/kline'
        params = {
            'code': contract,
            'start': get_market_now().strftime('%Y%m%d') + '000000',
            'number': '1',
            'type': '5'
        }
        resp = requests.get(url, params=params, timeout=3)
        result = resp.json()

        if result and result.get('Data') and len(result['Data']) > 0:
            d = result['Data'][0]
            now = get_market_now()
            return {
                'open': d[1] / 100 if d[1] else 0,
                'high': d[2] / 100 if d[2] else 0,
                'low': d[3] / 100 if d[3] else 0,
                'price': d[4] / 100 if d[4] else 0,
                'volume': d[5] if d[5] else 0,
                'hold': 0,
                'yesterday_close': 0,
                'date': now.strftime('%Y-%m-%d'),
                'time': now.strftime('%H:%M:%S'),
                'source': f'和讯({contract})',
                'contract': contract
            }
        return None
    except Exception as e:
        print(f"和讯接口失败: {e}")
        return None


def get_realtime_price(verify_all=True):
    """
    获取IF季月合约实时行情（带多个备用接口和数据验证）

    参数:
        verify_all: 如果为True，则获取所有数据源并验证一致性；否则使用第一个成功源

    返回: dict with keys: price, open, high, low, date, time, yesterday_close, source, contract, sources_info
          或 None（如果所有接口都失败）
    """
    # 接口优先级列表（全部获取季月合约数据）
    providers = [
        ('新浪季月', _get_realtime_sina),
        ('东方财富季月', _get_realtime_eastmoney),
        ('和讯季月', _get_realtime_hexun),
    ]

    if not verify_all:
        # 旧的行为：返回第一个成功的
        for name, func in providers:
            try:
                result = func()
                if result and result.get('price', 0) > 0:
                    return result
            except Exception as e:
                print(f"{name}接口异常: {e}")
                continue
        print("所有实时行情接口均失败")
        return None

    # 新的行为：验证所有数据源
    sources_results = {}
    sources_info = []

    for name, func in providers:
        try:
            result = func()
            if result and result.get('price', 0) > 0:
                sources_results[name] = result
                sources_info.append({
                    'source': name,
                    'price': result.get('price', 0),
                    'time': result.get('time', ''),
                    'status': '成功'
                })
                print(f"{name}: {result.get('price', 0)}")
            else:
                sources_info.append({'source': name, 'status': '无数据'})
        except Exception as e:
            sources_info.append({'source': name, 'status': f'失败: {str(e)[:30]}'})
            print(f"{name}接口异常: {e}")

    if not sources_results:
        print("所有实时行情接口均失败")
        return None

    # 选择最可靠的结果（多数来源或第一个）
    result = list(sources_results.values())[0]
    result['sources_info'] = sources_info
    result['sources_count'] = len(sources_results)

    # 数据一致性检查
    if len(sources_results) > 1:
        prices = [r.get('price', 0) for r in sources_results.values()]
        price_variance = max(prices) - min(prices)
        result['price_variance'] = price_variance

        # 盘中时间差异导致的价格差异可以接受（设置容差为1点）
        if price_variance <= 1:
            result['consistency_check'] = '✓ 数据一致'
        else:
            result['consistency_check'] = f'⚠ 数据差异{price_variance:.0f}点（可能因盘中时间差）'

    return result


def _get_yesterday_kline():
    """
    获取前一交易日的完整K线数据（OHLCV）
    通过新浪日K线API获取最近几天的数据，取前一交易日
    """
    try:
        contract = _get_current_quarterly_contract()
        # 新浪期货日K线接口
        url = f'https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20_result=/InnerFuturesNewService.getDailyKLine'
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
            return None

        import json
        data = json.loads(text[start+1:end+1])

        if not data or len(data) < 2:
            return None

        # 取倒数第二条数据（前一交易日）
        # 数据格式: {d: "2026-01-20", o: "4731.6", h: "4743.8", l: "4672.8", c: "4708.6", v: "69659"}
        yesterday = data[-2] if len(data) >= 2 else None
        if yesterday:
            return {
                'date': yesterday.get('d', ''),
                'open': float(yesterday.get('o', 0)),
                'high': float(yesterday.get('h', 0)),
                'low': float(yesterday.get('l', 0)),
                'close': float(yesterday.get('c', 0)),
                'volume': int(float(yesterday.get('v', 0))),
                'contract': contract
            }
        return None
    except Exception as e:
        print(f"获取前一交易日K线失败: {e}")
        return None


def is_trading_date(date):
    """
    检查指定日期是否是交易日
    参数: date - datetime.date 对象
    返回: True/False
    """
    # 周末不是交易日
    if date.weekday() >= 5:
        return False

    # 国内期货市场假日（2024-2026年主要假日）
    # 这是一个基础列表，需要根据实际情况更新
    holidays = {
        # 2024年
        (2024, 1, 1),   # 元旦
        (2024, 2, 10), (2024, 2, 11), (2024, 2, 12), (2024, 2, 13), (2024, 2, 14), (2024, 2, 15), (2024, 2, 16), (2024, 2, 17),  # 春节
        (2024, 4, 4), (2024, 4, 5), (2024, 4, 6),  # 清明
        (2024, 5, 1), (2024, 5, 2), (2024, 5, 3), (2024, 5, 4), (2024, 5, 5),  # 劳动节
        (2024, 6, 10),  # 端午
        (2024, 9, 15), (2024, 9, 16), (2024, 9, 17),  # 中秋
        (2024, 9, 18),  # 调休
        (2024, 10, 1), (2024, 10, 2), (2024, 10, 3), (2024, 10, 4), (2024, 10, 5), (2024, 10, 6), (2024, 10, 7),  # 国庆
        # 2025年
        (2025, 1, 1),  # 元旦
        (2025, 1, 29), (2025, 1, 30), (2025, 1, 31), (2025, 2, 1), (2025, 2, 2), (2025, 2, 3), (2025, 2, 4),  # 春节
        (2025, 4, 4), (2025, 4, 5), (2025, 4, 6),  # 清明
        (2025, 5, 1), (2025, 5, 2), (2025, 5, 3), (2025, 5, 4), (2025, 5, 5),  # 劳动节
        (2025, 6, 2),  # 端午
        (2025, 10, 1), (2025, 10, 2), (2025, 10, 3), (2025, 10, 4), (2025, 10, 5), (2025, 10, 6), (2025, 10, 7),  # 国庆
        # 2026年
        (2026, 1, 1),  # 元旦
        (2026, 2, 17), (2026, 2, 18), (2026, 2, 19), (2026, 2, 20), (2026, 2, 21), (2026, 2, 22), (2026, 2, 23), (2026, 2, 24),  # 春节
    }

    return (date.year, date.month, date.day) not in holidays


def is_trading_time():
    """
    判断当前是否在交易时段内
    股指期货交易时间：
    - 上午：9:30 - 11:30
    - 下午：13:00 - 15:00
    返回: (is_trading_day, is_trading_hours, time_hint)
    """
    now = get_market_now()
    today = now.date()
    weekday = now.weekday()  # 0=周一, 6=周日
    hour = now.hour
    minute = now.minute
    current_time = hour * 60 + minute  # 转为分钟数便于比较

    # 周末不是交易日
    if weekday >= 5:
        return False, False, "周末休市"

    # 检查是否是国家假日
    if not is_trading_date(today):
        return False, False, "假日休市"

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


# 注：get_data_path() 函数已统一到 path_manager 模块
# 直接使用 from path_manager import get_data_path


def get_quarterly_contracts(start_year=2017, end_year=2030):
    """生成季月合约代码列表（3月、6月、9月、12月）"""
    contracts = []
    for year in range(start_year, end_year + 1):
        for month in [3, 6, 9, 12]:
            code = f"IF{year % 100:02d}{month:02d}"
            contracts.append(code)
    return contracts


def get_delivery_date(year, month):
    """计算某月的交割日（第三个周五）"""
    first_day = datetime(year, month, 1)
    weekday = first_day.weekday()
    if weekday <= 4:
        first_friday = first_day + timedelta(days=(4 - weekday))
    else:
        first_friday = first_day + timedelta(days=(11 - weekday))
    third_friday = first_friday + timedelta(days=14)
    return third_friday


def get_current_quarterly_contract():
    """获取当前应该使用的季月合约代码"""
    today = get_market_now()
    year = today.year
    month = today.month

    # 季月列表
    quarterly_months = [3, 6, 9, 12]

    # 找到当前或下一个季月
    for qm in quarterly_months:
        if qm >= month:
            delivery = get_delivery_date(year, qm)
            if today.date() <= delivery.date():
                return f"IF{year % 100:02d}{qm:02d}"

    # 如果当年季月都过了，使用下一年3月
    return f"IF{(year + 1) % 100:02d}03"


def update_quarterly_data_akshare():
    """
    使用 akshare 更新季月合约数据
    需要安装: pip install akshare
    """
    try:
        import akshare as ak
        from datetime import datetime

        print("  [akshare] 正在从akshare获取IF季月合约数据...")

        # 获取数据路径
        data_path = get_data_path()
        file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')
        print(f"  [DEBUG] 数据文件路径: {file_path}")
        print(f"  [DEBUG] 数据目录可写: {os.access(data_path, os.W_OK)}")

        # 读取现有数据
        print("  [akshare] 读取现有数据...")
        if os.path.exists(file_path):
            try:
                df_old = pd.read_csv(file_path)
                df_old['日期'] = pd.to_datetime(df_old['日期'])

                # 标准化列：确保价格数据在正确的列中
                for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
                    if old_col in df_old.columns and new_col in df_old.columns:
                        mask = df_old[new_col].isna()
                        if mask.any():
                            df_old.loc[mask, new_col] = df_old.loc[mask, old_col]

                last_date = df_old['日期'].max()
                print(f"  [DEBUG] 现有数据行数: {len(df_old)}")
                print(f"  [DEBUG] 现有数据最新日期: {last_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                print(f"  [WARNING] 读取现有数据失败: {e}")
                df_old = None
                last_date = datetime(2017, 1, 1)
        else:
            print(f"  [DEBUG] CSV文件不存在，将创建新文件")
            df_old = None
            last_date = datetime(2017, 1, 1)

        # 获取当前季月合约
        print("  [akshare] 确定当前季月合约...")
        current_contract = get_current_quarterly_contract()
        print(f"  [DEBUG] 当前季月合约: {current_contract}")

        # 获取该合约的数据
        print(f"  [akshare] 从 akshare 获取 {current_contract} 的日线数据...")
        try:
            # 使用中金所数据
            symbol = current_contract
            print(f"  [DEBUG] 调用 ak.futures_zh_daily_sina(symbol='{symbol}')...")
            df_new = ak.futures_zh_daily_sina(symbol=symbol)
            print(f"  [DEBUG] akshare 返回数据: {type(df_new)}")

            if df_new is not None and len(df_new) > 0:
                print(f"  [DEBUG] 获取到 {len(df_new)} 条原始数据")
                print(f"  [DEBUG] 数据列: {list(df_new.columns)}")

                # 重命名列
                print(f"  [akshare] 重命名数据列...")
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
                print(f"  [DEBUG] 重命名后的列: {list(df_new.columns)}")

                # 只保留比现有数据更新的记录
                print(f"  [akshare] 过滤新数据...")
                if df_old is not None:
                    before_filter = len(df_new)
                    df_new = df_new[df_new['日期'] > last_date]
                    print(f"  [DEBUG] 过滤前 {before_filter} 条 → 过滤后 {len(df_new)} 条")

                if len(df_new) > 0:
                    print(f"  [akshare] 获取到 {len(df_new)} 条新数据")

                    # 合并数据
                    print(f"  [akshare] 合并数据...")
                    required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '持仓量', '合约']

                    if df_old is not None:
                        # 确保旧数据有合约列
                        if '合约' not in df_old.columns:
                            df_old['合约'] = ''
                        df_old = df_old[[c for c in required_cols if c in df_old.columns]]
                        print(f"  [DEBUG] 旧数据行数: {len(df_old)}")

                    df_new = df_new[[c for c in required_cols if c in df_new.columns]]

                    if df_old is not None:
                        df = pd.concat([df_old, df_new], ignore_index=True)
                        print(f"  [DEBUG] 合并后行数: {len(df)}")
                    else:
                        df = df_new
                        print(f"  [DEBUG] 使用新数据（无旧数据）: {len(df)} 行")

                    # 去重和排序
                    print(f"  [akshare] 去重和排序...")
                    df = df.drop_duplicates(subset=['日期'], keep='last')
                    df = df.sort_values('日期').reset_index(drop=True)
                    print(f"  [DEBUG] 最终数据行数: {len(df)}")

                    # 保存文件
                    print(f"  [akshare] 保存数据到 {file_path}...")
                    df.to_csv(file_path, index=False)

                    # 验证保存
                    if os.path.exists(file_path):
                        saved_size = os.path.getsize(file_path)
                        print(f"  [DEBUG] 文件保存成功，大小: {saved_size} 字节")

                        # 验证读取
                        df_verify = pd.read_csv(file_path)
                        print(f"  [DEBUG] 验证读取: {len(df_verify)} 行")
                        latest_date = pd.to_datetime(df_verify['日期']).max()
                        print(f"  [DEBUG] 最新日期: {latest_date.strftime('%Y-%m-%d')}")
                    else:
                        raise Exception("文件保存失败：文件不存在")

                    return f"✓ 数据更新成功\n合约: {current_contract}\n共 {len(df)} 条记录\n最新日期: {df['日期'].max().strftime('%Y-%m-%d')}"
                else:
                    # 检查是否在交易时段，给出更友好的提示
                    print(f"  [akshare] 无新数据（已是最新）")
                    is_trading_day, is_trading_hours, time_hint = is_trading_time()
                    today = get_market_now().date()

                    if is_trading_day and last_date.date() < today:
                        # 今天是交易日但数据还没更新到今天
                        print(f"  [DEBUG] 今天是交易日但数据未更新")
                        return f"数据最新日期: {last_date.strftime('%Y-%m-%d')}\n{time_hint}"
                    else:
                        print(f"  [DEBUG] 数据已是最新")
                        return f"数据已是最新，最新日期: {last_date.strftime('%Y-%m-%d')}"
            else:
                print(f"  [ERROR] akshare 返回空数据: {df_new}")
                raise Exception("akshare 返回空数据，可能是网络问题或合约代码错误")

        except Exception as e:
            error_msg = str(e)
            print(f"  [ERROR] 获取合约 {current_contract} 数据失败")
            print(f"  [ERROR] 错误详情: {error_msg[:200]}")
            raise Exception(f"akshare 获取数据失败: {error_msg[:300]}")

    except ImportError:
        raise Exception("请先安装akshare: pip install akshare")
    except Exception as e:
        raise Exception(f"akshare更新失败: {str(e)}")


def update_from_main_contract():
    """更新IF季月合约数据（基于现有CSV + 当天实时数据）"""
    try:
        print("正在更新IF季月合约数据...")

        data_path = get_data_path()
        file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

        # 读取现有的季月合约连接数据
        if not os.path.exists(file_path):
            raise Exception("数据文件不存在，请先手动下载历史数据")

        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df['日期'] = pd.to_datetime(df['日期'])

        # 标准化列名
        for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]

        required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '持仓量', '合约']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0 if col != '合约' else ''

        df = df[[c for c in required_cols if c in df.columns]]
        df = df.sort_values('日期').reset_index(drop=True)

        # 根据日期推断季月合约的函数
        def infer_quarterly_contract(date):
            year = date.year
            month = date.month
            quarterly_months = [3, 6, 9, 12]
            for qm in quarterly_months:
                if qm >= month:
                    delivery = get_delivery_date(year, qm)
                    if date.date() <= delivery.date():
                        return f"IF{year % 100:02d}{qm:02d}"
            return f"IF{(year + 1) % 100:02d}03"

        # 如果是交易日，获取当前季月合约的实时数据
        today = get_market_now().date()
        latest_date = df['日期'].max().date()
        current_contract = _get_current_quarterly_contract()

        is_trade_day, is_trade_hours, time_hint = is_trading_time()

        # 获取季月合约实时行情（启用多源验证）
        print("\n【正在查询多数据源】")
        print("  数据源1: 新浪财经 (新浪季月)")
        print("  数据源2: 东方财富 (东方财富季月)")
        print("  数据源3: 和讯期货 (和讯季月)")
        print()
        realtime = get_realtime_price(verify_all=True)

        if realtime and realtime.get('price', 0) > 0:
            # 准备详细的数据源信息反馈
            sources_info = realtime.get('sources_info', [])
            # ========== 修正前一交易日完整OHLC数据 ==========
            # 尝试获取前一交易日的完整K线数据来修正
            yesterday_kline = _get_yesterday_kline()

            if yesterday_kline and yesterday_kline.get('close', 0) > 0:
                # 使用完整K线数据修正
                kline_date = yesterday_kline.get('date', '')
                if kline_date:
                    kline_date_dt = pd.to_datetime(kline_date)
                    last_idx = df[df['日期'] == kline_date_dt].index

                    if len(last_idx) > 0:
                        idx = last_idx[0]
                        corrections = []

                        # 检查并修正各个字段
                        for field, api_field in [('开盘', 'open'), ('最高', 'high'), ('最低', 'low'), ('收盘', 'close')]:
                            old_val = df.loc[idx, field]
                            new_val = yesterday_kline.get(api_field, 0)
                            if new_val > 0 and abs(old_val - new_val) > 0.1:
                                df.loc[idx, field] = new_val
                                corrections.append(f"{field}:{old_val}→{new_val}")

                        # 修正成交量
                        old_vol = df.loc[idx, '成交量']
                        new_vol = yesterday_kline.get('volume', 0)
                        if new_vol > 0 and old_vol != new_vol:
                            df.loc[idx, '成交量'] = new_vol
                            corrections.append(f"成交量:{old_vol}→{new_vol}")

                        if corrections:
                            print(f"已修正{kline_date}数据: {', '.join(corrections)}")
            else:
                # 备选：仅使用实时API的昨收价修正收盘价
                yesterday_close = realtime.get('yesterday_close', 0)
                if yesterday_close > 0:
                    df_before_today = df[df['日期'].dt.date < today]
                    if len(df_before_today) > 0:
                        last_trading_day = df_before_today['日期'].max()
                        last_idx = df[df['日期'] == last_trading_day].index

                        if len(last_idx) > 0:
                            idx = last_idx[0]
                            old_close = df.loc[idx, '收盘']

                            if abs(old_close - yesterday_close) > 0.1:
                                df.loc[idx, '收盘'] = yesterday_close
                                print(f"已修正{last_trading_day.strftime('%Y-%m-%d')}收盘价: {old_close} → {yesterday_close}")

            # ========== 更新当天数据 ==========
            # 增强检查：确保只有真正的交易日才添加数据
            if is_trade_day and is_trading_date(today):
                # 验证返回的日期也应该是交易日
                returned_date_str = realtime.get('date', '')
                if returned_date_str:
                    try:
                        returned_date = pd.to_datetime(returned_date_str).date()
                        # 检查返回的日期是否有效（不应该是周末）
                        if returned_date.weekday() >= 5:
                            print(f"⚠️ 警告：API返回的日期{returned_date}是周末，忽略此数据")
                            if is_trade_day:
                                print(f"非交易日，数据最新日期: {latest_date}")
                            return f"非交易日，数据保持不变，最新日期: {latest_date}{sources_text}"
                    except:
                        pass

                today_row = {
                    '日期': pd.Timestamp(today),
                    '开盘': realtime.get('open', realtime['price']),
                    '最高': realtime.get('high', realtime['price']),
                    '最低': realtime.get('low', realtime['price']),
                    '收盘': realtime['price'],
                    '成交量': realtime.get('volume', 0),
                    '持仓量': 0,
                    '合约': current_contract
                }

                # 移除今天的旧数据（如果有）
                df = df[df['日期'].dt.date != today]
                # 添加今天的新数据
                df = pd.concat([df, pd.DataFrame([today_row])], ignore_index=True)
                df = df.sort_values('日期').reset_index(drop=True)

                print(f"已更新今日{current_contract}实时数据: {realtime['price']}")

            df.to_csv(file_path, index=False, encoding='utf-8-sig')

            # 构建详细反馈信息
            sources_text = ""
            if sources_info:
                sources_text += "\n【数据来源验证】\n"
                success_count = sum(1 for s in sources_info if s.get('status') == '成功')
                for info in sources_info:
                    status = info['status']
                    # 为成功的源添加✓标记
                    if status == '成功':
                        sources_text += f"  ✓ {info['source']}: {status}"
                        if info.get('price'):
                            sources_text += f" ({info['price']})"
                    else:
                        sources_text += f"  ✗ {info['source']}: {status}"
                    sources_text += "\n"

                if success_count > 1:
                    sources_text += f"\n✓ 多源验证: {success_count}个数据源都已确认\n"
                    if realtime.get('consistency_check'):
                        sources_text += f"{realtime['consistency_check']}\n"
                    if realtime.get('price_variance'):
                        sources_text += f"（最大价差: {realtime['price_variance']:.0f}点）\n"

                sources_text += f"→ 本次使用数据源: {realtime['source']}\n"

            if is_trade_day:
                return (f"✓ 数据更新成功\n"
                        f"合约: {current_contract}\n"
                        f"最新价: {realtime['price']}\n"
                        f"获取时间: {realtime.get('time', '(本地)')}"
                        f"{sources_text}")
            else:
                return f"非交易日，已校验历史数据，最新日期: {latest_date}{sources_text}"
        else:
            if is_trade_day:
                return f"✗ 获取实时行情失败，数据保持不变，最新日期: {latest_date}"
            else:
                return f"非交易日，数据最新日期: {latest_date}"

    except Exception as e:
        raise Exception(f"数据更新失败: {str(e)}")


def update_if_data():
    """
    自动更新IF季月合约数据
    优先级: akshare → 东方财富 → 主连推断
    （所有环境统一使用这个优先级，避免复杂的条件判断）
    """
    from datetime import datetime

    start_time = datetime.now()
    print("\n" + "="*70)
    print(f"[IF300] 数据更新开始 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    try:
        # 获取数据路径
        data_path = get_data_path()
        print(f"[DEBUG] 数据路径: {data_path}")

        # 检查文件是否存在
        file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')
        file_exists = os.path.exists(file_path)
        print(f"[DEBUG] CSV文件存在: {file_exists}")
        if file_exists:
            file_size = os.path.getsize(file_path)
            print(f"[DEBUG] CSV文件大小: {file_size} 字节")

        # 获取当前合约
        current_contract = _get_current_quarterly_contract()
        print(f"[DEBUG] 当前季月合约: {current_contract}")

        # 检查环境
        env_type = "Windows EXE" if getattr(sys, 'frozen', False) else "开发环境"
        print(f"[DEBUG] 运行环境: {env_type}")

        print(f"\n[IF300] 优先级: akshare → 东方财富 → 主连推断")

        # 1️⃣ 优先使用 akshare（最稳定，获取完整日线数据）
        print("\n" + "-"*70)
        print("[Step 1/3] 尝试 akshare 数据源...")
        print("-"*70)
        try:
            result = update_quarterly_data_akshare()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n✅ akshare 更新成功！(耗时: {elapsed:.1f}秒)")
            print(f"[Result] {result}")
            print("="*70 + "\n")
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ akshare 失败")
            print(f"[Error] {error_msg[:200]}")

        # 2️⃣ 备选1: 东方财富 API（获取完整日线）
        print("\n" + "-"*70)
        print("[Step 2/3] 尝试东方财富 API...")
        print("-"*70)
        try:
            result = update_quarterly_from_eastmoney()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n✅ 东方财富 API 更新成功！(耗时: {elapsed:.1f}秒)")
            print(f"[Result] {result}")
            print("="*70 + "\n")
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 东方财富 API 失败")
            print(f"[Error] {error_msg[:200]}")

        # 3️⃣ 备选2: 主连推断方法（只在前两个失败时使用）
        print("\n" + "-"*70)
        print("[Step 3/3] 尝试主连推断方法（备选）...")
        print("-"*70)
        try:
            result = update_from_main_contract()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n✅ 主连推断方法更新成功！(耗时: {elapsed:.1f}秒)")
            print(f"[Result] {result}")
            print("="*70 + "\n")
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 主连推断方法也失败")
            print(f"[Error] {error_msg[:200]}")
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n❌ 数据更新失败！(耗时: {elapsed:.1f}秒)")
            print("="*70)
            raise Exception(f"数据更新失败（所有数据源均无法获取完整日线数据）\n错误信息: {error_msg[:300]}")

    except Exception as e:
        print(f"\n[FATAL] 未预期的错误: {str(e)[:200]}")
        print("="*70 + "\n")
        raise


def update_quarterly_from_eastmoney():
    """
    从东方财富获取 IF 季月合约日线数据（稳定方案）
    不依赖多个接口，相对可靠，适合 Windows EXE 环境
    """
    try:
        print("[IF300-EMY] 正在从东方财富获取 IF 季月合约数据...")

        data_path = get_data_path()
        file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

        current_contract = _get_current_quarterly_contract()
        print(f"[IF300-EMY] 当前季月合约: {current_contract}")

        # 东方财富期货日线 API
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': f'8.{current_contract}',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57',
            'klt': '101',      # 日线
            'fqt': '0',        # 不复权
            'beg': '20150101',
            'end': '20500101',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'smplmt': '5000',
            'lmt': '5000'
        }

        print(f"[IF300-EMY] 请求 URL: {url}")
        resp = requests.get(url, params=params, timeout=30)
        result = resp.json()

        if result.get('data') and result['data'].get('klines'):
            klines = result['data']['klines']
            print(f"[IF300-EMY] 获取到 {len(klines)} 条 K 线数据")

            rows = []
            for line in klines:
                try:
                    parts = line.split(',')
                    if len(parts) >= 6:
                        rows.append({
                            '日期': parts[0],
                            '开盘': float(parts[1]),
                            '收盘': float(parts[2]),
                            '最高': float(parts[3]),
                            '最低': float(parts[4]),
                            '成交量': int(float(parts[5])),
                            '持仓量': 0,
                            '合约': current_contract
                        })
                except Exception as e:
                    print(f"[IF300-EMY] 警告：解析数据行失败: {e}")
                    continue

            if not rows:
                return f"✗ 未获取到有效数据，请检查合约代码: {current_contract}"

            df = pd.DataFrame(rows)
            df['日期'] = pd.to_datetime(df['日期'])

            # 与现有数据合并
            if os.path.exists(file_path):
                try:
                    print(f"[IF300-EMY] 读取现有数据文件...")
                    df_old = pd.read_csv(file_path, encoding='utf-8-sig')
                    df_old['日期'] = pd.to_datetime(df_old['日期'])

                    required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '持仓量', '合约']
                    df_old = df_old[[c for c in required_cols if c in df_old.columns]]

                    print(f"[IF300-EMY] 现有数据: {len(df_old)} 行，新数据: {len(df)} 行")
                    df = pd.concat([df_old, df], ignore_index=True)
                    df = df.drop_duplicates(subset=['日期'], keep='last')
                except Exception as e:
                    print(f"[IF300-EMY] 警告：合并失败，将使用新数据: {e}")

            df = df.sort_values('日期').reset_index(drop=True)

            # ✓ 保存文件
            print(f"[IF300-EMY] 保存数据到: {file_path}")
            df.to_csv(file_path, index=False, encoding='utf-8-sig')

            # ✓ 验证保存
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                df_verify = pd.read_csv(file_path)
                print(f"[IF300-EMY] ✓ 验证成功: 文件大小 {file_size} bytes, 数据行数 {len(df_verify)}")

                return (f"✓ 数据更新成功 (东方财富)\n"
                        f"合约: {current_contract}\n"
                        f"共 {len(df)} 条记录\n"
                        f"日期范围: {df['日期'].min().strftime('%Y-%m-%d')} ~ {df['日期'].max().strftime('%Y-%m-%d')}")
            else:
                raise Exception(f"文件保存失败: {file_path}")

        else:
            error_msg = result.get('message', '未知错误')
            return f"✗ 未从东方财富获取到数据: {error_msg}"

    except Exception as e:
        print(f"[IF300-EMY] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"东方财富 API 更新失败: {str(e)}")


def check_data_status():
    """检查数据状态"""
    data_path = get_data_path()
    file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

    if not os.path.exists(file_path):
        return {
            'exists': False,
            'message': '数据文件不存在'
        }

    df = pd.read_csv(file_path)
    df['日期'] = pd.to_datetime(df['日期'])

    latest_date = df['日期'].max()
    today = get_market_now().date()
    days_behind = (today - latest_date.date()).days

    # 获取最新合约
    latest_contract = df.iloc[-1].get('合约', '未知')

    return {
        'exists': True,
        'records': len(df),
        'start_date': df['日期'].min().strftime('%Y-%m-%d'),
        'end_date': latest_date.strftime('%Y-%m-%d'),
        'days_behind': days_behind,
        'latest_contract': latest_contract,
        'needs_update': days_behind > 1,
        'message': f"数据共{len(df)}条，合约:{latest_contract}，最新: {latest_date.strftime('%Y-%m-%d')}，落后{days_behind}天"
    }


if __name__ == '__main__':
    print("检查数据状态...")
    status = check_data_status()
    print(status['message'])

    if status.get('needs_update', True):
        print("\n尝试更新数据...")
        try:
            result = update_if_data()
            print(result)
        except Exception as e:
            print(f"更新失败: {e}")
