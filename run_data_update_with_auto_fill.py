#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IF300 数据更新 - 自动缺口补全版本（推荐）

这个脚本提供了改进的数据更新功能：
1. 检测数据中的缺口（缺失的交易日）
2. 自动从新浪API获取历史K线数据
3. 自动补全所有缺失的交易日

使用方法：
  python run_data_update_with_auto_fill.py
"""

import sys
import os

# 确保可以导入data_updater_v2模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_updater_v2 import update_if_data_with_auto_fill


def main():
    """主函数"""
    print("\n" + "="*80)
    print("IF300 数据更新 - 自动缺口补全版本")
    print("="*80)
    print("\n这个程序会：")
    print("  1. 执行标准数据更新（获取最新交易数据）")
    print("  2. 检测数据中的缺口（缺失的交易日）")
    print("  3. 自动从新浪API补全缺失数据")
    print("  4. 保存更新后的完整数据")
    print("\n" + "-"*80 + "\n")

    try:
        update_if_data_with_auto_fill()
        print("\n✅ 数据更新完成！\n")
    except Exception as e:
        print(f"\n❌ 错误: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
