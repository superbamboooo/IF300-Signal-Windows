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


def _get_current_quarterly_contract():
    """获取当前季月合约代码"""
    now = datetime.now()
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

        now = datetime.now()
        return {
            'open': float(data[0]) if data[0] else 0,
            'high': float(data[1]) if data[1] else 0,
            'low': float(data[2]) if data[2] else 0,
            'price': float(data[3]) if data[3] else 0,
            'volume': int(float(data[4])) if data[4] else 0,
            'hold': float(data[6]) if len(data) > 6 and data[6] else 0,
            'yesterday_close': float(data[13]) if len(data) > 13 and data[13] else 0,
            'date': data[36] if len(data) > 36 else now.strftime('%Y-%m-%d'),
            'time': data[37] if len(data) > 37 else now.strftime('%H:%M:%S'),
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
                now = datetime.now()
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
            'start': datetime.now().strftime('%Y%m%d') + '000000',
            'number': '1',
            'type': '5'
        }
        resp = requests.get(url, params=params, timeout=3)
        result = resp.json()

        if result and result.get('Data') and len(result['Data']) > 0:
            d = result['Data'][0]
            now = datetime.now()
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


def is_trading_time():
    """
    判断当前是否在交易时段内
    股指期货交易时间：
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
    today = datetime.now()
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

        print("正在从akshare获取IF季月合约数据...")

        data_path = get_data_path()
        file_path = os.path.join(data_path, 'IF_主连_季月合约连接_day.csv')

        # 读取现有数据
        if os.path.exists(file_path):
            df_old = pd.read_csv(file_path)
            df_old['日期'] = pd.to_datetime(df_old['日期'])

            # 标准化列：确保价格数据在正确的列中
            for old_col, new_col in [('开盘价', '开盘'), ('最高价', '最高'), ('最低价', '最低'), ('收盘价', '收盘')]:
                if old_col in df_old.columns and new_col in df_old.columns:
                    mask = df_old[new_col].isna()
                    if mask.any():
                        df_old.loc[mask, new_col] = df_old.loc[mask, old_col]

            last_date = df_old['日期'].max()
            print(f"现有数据最新日期: {last_date.strftime('%Y-%m-%d')}")
        else:
            df_old = None
            last_date = datetime(2017, 1, 1)

        # 获取当前季月合约
        current_contract = get_current_quarterly_contract()
        print(f"当前季月合约: {current_contract}")

        # 获取该合约的数据
        try:
            # 使用中金所数据
            symbol = current_contract
            df_new = ak.futures_zh_daily_sina(symbol=symbol)

            if df_new is not None and len(df_new) > 0:
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

                # 只保留比现有数据更新的记录
                if df_old is not None:
                    df_new = df_new[df_new['日期'] > last_date]

                if len(df_new) > 0:
                    print(f"获取到 {len(df_new)} 条新数据")

                    # 合并数据
                    required_cols = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '持仓量', '合约']

                    if df_old is not None:
                        # 确保旧数据有合约列
                        if '合约' not in df_old.columns:
                            df_old['合约'] = ''
                        df_old = df_old[[c for c in required_cols if c in df_old.columns]]

                    df_new = df_new[[c for c in required_cols if c in df_new.columns]]

                    if df_old is not None:
                        df = pd.concat([df_old, df_new], ignore_index=True)
                    else:
                        df = df_new

                    df = df.drop_duplicates(subset=['日期'], keep='last')
                    df = df.sort_values('日期').reset_index(drop=True)

                    df.to_csv(file_path, index=False)

                    return f"数据更新成功，共{len(df)}条记录，最新日期: {df['日期'].max().strftime('%Y-%m-%d')}"
                else:
                    # 检查是否在交易时段，给出更友好的提示
                    is_trading_day, is_trading_hours, time_hint = is_trading_time()
                    today = datetime.now().date()

                    if is_trading_day and last_date.date() < today:
                        # 今天是交易日但数据还没更新到今天
                        return f"数据最新日期: {last_date.strftime('%Y-%m-%d')}\n{time_hint}"
                    else:
                        return f"数据已是最新，最新日期: {last_date.strftime('%Y-%m-%d')}"
            else:
                return "未获取到新数据"

        except Exception as e:
            print(f"获取合约 {current_contract} 数据失败: {e}")
            # 尝试使用主连数据作为备选
            return update_from_main_contract()

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
        today = datetime.now().date()
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
            if is_trade_day:
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
    优先使用主连推断方法（支持多源验证），akshare作为备选
    """
    # 优先使用主连推断方法（支持多源数据验证）
    try:
        return update_from_main_contract()
    except Exception as e:
        print(f"主连推断方法失败: {e}，尝试akshare")
        # 备选：尝试akshare
        try:
            return update_quarterly_data_akshare()
        except Exception as e2:
            raise Exception(f"数据更新失败: {str(e2)}")


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
    today = datetime.now().date()
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
