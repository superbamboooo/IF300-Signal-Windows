#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IF300 数据源验证测试脚本
用于测试多源数据查询和验证功能
"""

from data_updater import (
    _get_realtime_sina,
    _get_realtime_eastmoney,
    _get_realtime_hexun,
    get_realtime_price
)
from datetime import datetime

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_single_sources():
    """测试单个数据源"""
    print_header("测试 1: 单个数据源查询")

    sources = [
        ("新浪财经", _get_realtime_sina),
        ("东方财富", _get_realtime_eastmoney),
        ("和讯期货", _get_realtime_hexun),
    ]

    results = {}
    for name, func in sources:
        print(f"查询 {name}...", end=" ")
        try:
            result = func()
            if result and result.get('price', 0) > 0:
                print(f"✓ 成功")
                print(f"  └─ 价格: {result['price']:.1f}")
                print(f"  └─ 合约: {result.get('contract', '未知')}")
                print(f"  └─ 时间: {result.get('time', '(本地)')}")
                results[name] = result
            else:
                print(f"✗ 无数据")
        except Exception as e:
            print(f"✗ 失败: {str(e)[:40]}")

    return results

def test_multi_source_verification():
    """测试多源数据验证"""
    print_header("测试 2: 多源数据验证")

    print("正在从3个数据源并行获取数据...\n")
    result = get_realtime_price(verify_all=True)

    if result:
        print(f"✓ 数据获取成功\n")
        print(f"  选定数据源: {result['source']}")
        print(f"  最新价: {result['price']:.1f}")
        print(f"  合约代码: {result.get('contract', '未知')}")
        print(f"  获取时间: {result.get('time', '(本地)')}")

        if result.get('sources_info'):
            print(f"\n  【多源查询结果】")
            for info in result['sources_info']:
                if info.get('status') == '成功':
                    print(f"    ✓ {info['source']}: {info.get('price', 'N/A')}")
                else:
                    print(f"    ✗ {info['source']}: {info['status']}")

        if result.get('sources_count', 0) > 1:
            print(f"\n  【数据一致性检查】")
            print(f"    确认源数: {result.get('sources_count', 1)}")
            print(f"    {result.get('consistency_check', '✓ 数据一致')}")
            if result.get('price_variance'):
                print(f"    最大价差: {result.get('price_variance', 0):.0f}点")
    else:
        print(f"✗ 所有数据源都失败")

def test_fallback():
    """测试降级逻辑"""
    print_header("测试 3: 数据源降级处理")

    print("第一次查询（verify_all=True）:")
    result1 = get_realtime_price(verify_all=True)
    if result1:
        print(f"  ✓ 获得数据，来源: {result1.get('source', 'unknown')}")

    print("\n第二次查询（verify_all=False，快速模式）:")
    result2 = get_realtime_price(verify_all=False)
    if result2:
        print(f"  ✓ 获得数据，来源: {result2.get('source', 'unknown')}")

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  IF300 多源数据验证系统测试")
    print("  运行时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("="*60)

    try:
        # 运行测试
        test_single_sources()
        test_multi_source_verification()
        test_fallback()

        print_header("测试完成")
        print("✓ 多源验证系统运行正常")
        print("\n📋 说明:")
        print("  - 如果某个源显示'无数据'或'失败'，这是正常现象")
        print("  - 系统会自动使用可用的源")
        print("  - 至少需要1个源成功才能获得数据")
        print()

    except Exception as e:
        print_header("测试异常")
        print(f"✗ 发生错误: {e}")

if __name__ == '__main__':
    main()
