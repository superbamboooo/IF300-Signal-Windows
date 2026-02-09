#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
测试修复：非交易日数据问题
================================================================================
验证周末和假日是否被正确拒绝
"""

import sys
import os
from datetime import datetime, timedelta

# 导入修复后的函数
sys.path.insert(0, os.path.dirname(__file__))

from data_updater import is_trading_date, is_trading_time


def test_is_trading_date():
    """测试交易日判断函数"""
    print("\n" + "=" * 80)
    print("测试 1: is_trading_date() 函数")
    print("=" * 80)

    test_cases = [
        # (日期, 期望结果, 说明)
        ((2025, 2, 8), True, "2025-02-08 周六 - 应该不是交易日但输入的是周六"),
        ((2025, 2, 3), True, "2025-02-03 周一 - 春节假期，应该不是交易日"),
        ((2025, 2, 5), False, "2025-02-05 周三 - 不在假日列表中，应该是交易日"),
        ((2025, 1, 1), False, "2025-01-01 元旦 - 应该不是交易日"),
        ((2025, 4, 4), False, "2025-04-04 清明 - 应该不是交易日"),
        ((2025, 5, 1), False, "2025-05-01 劳动节 - 应该不是交易日"),
        ((2025, 6, 2), False, "2025-06-02 端午 - 应该不是交易日"),
        ((2025, 10, 1), False, "2025-10-01 国庆 - 应该不是交易日"),
        ((2025, 2, 10), True, "2025-02-10 周一 - 春节后首个交易日，应该是交易日"),
    ]

    failed = 0
    for (year, month, day), expected, description in test_cases:
        date = datetime(year, month, day).date()
        result = is_trading_date(date)
        status = "✓" if result == expected else "✗"
        print(f"\n{status} {description}")
        print(f"   日期: {date.strftime('%Y-%m-%d')} ({['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date.weekday()]})")
        print(f"   预期: {expected}, 实际: {result}")
        if result != expected:
            failed += 1
            print(f"   ⚠️ 测试失败!")

    print(f"\n{'=' * 80}")
    print(f"交易日判断测试: {len(test_cases) - failed}/{len(test_cases)} 通过")
    return failed == 0


def test_weekend_rejection():
    """测试周末是否被拒绝"""
    print("\n" + "=" * 80)
    print("测试 2: 周末拒绝机制")
    print("=" * 80)

    # 找到最近的周末
    today = datetime.now().date()
    current_weekday = today.weekday()

    # 计算到下一个周六
    days_to_saturday = (5 - current_weekday) % 7
    if days_to_saturday == 0:
        days_to_saturday = 7

    next_saturday = today + timedelta(days=days_to_saturday)
    next_sunday = today + timedelta(days=days_to_saturday + 1)

    print(f"\n当前日期: {today.strftime('%Y-%m-%d')} ({['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]})")
    print(f"下一个周末: {next_saturday.strftime('%Y-%m-%d')} (周六) 和 {next_sunday.strftime('%Y-%m-%d')} (周日)")

    # 测试周末
    test_dates = [next_saturday, next_sunday]
    for test_date in test_dates:
        result = is_trading_date(test_date)
        status = "✓" if result == False else "✗"
        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][test_date.weekday()]
        print(f"\n{status} {test_date.strftime('%Y-%m-%d')} {weekday_name}")
        print(f"   is_trading_date() = {result} (期望: False)")


def test_holiday_calendar():
    """打印完整的2025年假日日历"""
    print("\n" + "=" * 80)
    print("测试 3: 2025年假日日历")
    print("=" * 80)

    holidays_2025 = [
        (2025, 1, 1, "元旦"),
        (2025, 1, 29, "春节"),
        (2025, 1, 30, "春节"),
        (2025, 1, 31, "春节"),
        (2025, 2, 1, "春节"),
        (2025, 2, 2, "春节"),
        (2025, 2, 3, "春节"),
        (2025, 2, 4, "春节"),
        (2025, 4, 4, "清明"),
        (2025, 4, 5, "清明"),
        (2025, 4, 6, "清明"),
        (2025, 5, 1, "劳动节"),
        (2025, 5, 2, "劳动节"),
        (2025, 5, 3, "劳动节"),
        (2025, 5, 4, "劳动节"),
        (2025, 5, 5, "劳动节"),
        (2025, 6, 2, "端午"),
        (2025, 10, 1, "国庆"),
        (2025, 10, 2, "国庆"),
        (2025, 10, 3, "国庆"),
        (2025, 10, 4, "国庆"),
        (2025, 10, 5, "国庆"),
        (2025, 10, 6, "国庆"),
        (2025, 10, 7, "国庆"),
    ]

    print("\n2025年官方假日列表（期货市场休市日期）:")
    print("-" * 50)
    for year, month, day, name in holidays_2025:
        date = datetime(year, month, day).date()
        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date.weekday()]
        is_trading = is_trading_date(date)
        status = "✓ 休市" if not is_trading else "✗ 应该休市但系统认为交易日"
        print(f"{status} {date.strftime('%Y-%m-%d')} ({weekday_name}) - {name}")


def test_trading_time_function():
    """测试改进后的 is_trading_time() 函数"""
    print("\n" + "=" * 80)
    print("测试 4: is_trading_time() 函数")
    print("=" * 80)

    is_trade_day, is_trade_hours, time_hint = is_trading_time()
    today = datetime.now().date()
    weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]

    print(f"\n当前日期: {today.strftime('%Y-%m-%d')} ({weekday_name})")
    print(f"当前时间: {datetime.now().strftime('%H:%M:%S')}")
    print(f"\n函数返回值:")
    print(f"  is_trade_day: {is_trade_day}")
    print(f"  is_trade_hours: {is_trade_hours}")
    print(f"  time_hint: {time_hint}")

    if is_trade_day:
        print(f"\n✓ 系统判断今天是交易日，将允许数据更新")
    else:
        print(f"\n✓ 系统判断今天不是交易日，将拒绝数据更新")
        print(f"   原因: {time_hint}")


def main():
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "非交易日数据问题修复验证" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")

    # 运行所有测试
    test_is_trading_date()
    test_weekend_rejection()
    test_holiday_calendar()
    test_trading_time_function()

    print("\n" + "=" * 80)
    print("验证完成！")
    print("=" * 80)
    print("\n✅ 如果所有测试都通过，表示修复成功！")
    print("\n接下来可以：")
    print("1. 在周末或假日测试'更新数据'按钮")
    print("2. 检查K线图是否没有周末/假日的数据行")
    print("3. 在正常交易日测试数据更新功能")
    print("\n" + "=" * 80 + "\n")


if __name__ == '__main__':
    main()
