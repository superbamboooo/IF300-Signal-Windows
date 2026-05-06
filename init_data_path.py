#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 数据路径初始化和诊断工具
================================================================================

功能：
1. 首次运行时检测和创建数据目录
2. 生成配置文件
3. 验证数据文件完整性
4. 提供交互式路径选择（可选）
5. 诊断路径配置问题

用法：
  python init_data_path.py                # 检查并初始化
  python init_data_path.py diagnose       # 输出诊断信息
  python init_data_path.py reset          # 重置配置文件

================================================================================
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 导入路径管理模块
try:
    from path_manager import get_data_path, CONFIG_FILE, CONFIG_DIR, diagnose
except ImportError:
    print("错误：无法导入 path_manager 模块")
    print("请确保 path_manager.py 在同一目录")
    sys.exit(1)


# ============================================================================
# 常量
# ============================================================================

REQUIRED_FILES = [
    'IF_主连_季月合约连接_day.csv',      # IF300策略历史数据
    '159915_创业板ETF_day.csv',           # 周末效应策略历史数据
]

# ============================================================================
# 初始化函数
# ============================================================================

def init_data_path():
    """初始化数据路径"""
    print("\n" + "=" * 70)
    print("IF300 数据路径初始化")
    print("=" * 70 + "\n")

    try:
        # 1. 获取数据路径（会自动创建）
        data_path = get_data_path()
        print(f"✓ 数据目录: {data_path}")

        # 2. 检查目录存在性
        if not os.path.exists(data_path):
            print("✗ 数据目录不存在，已创建")
            os.makedirs(data_path, exist_ok=True)
        else:
            print("✓ 数据目录已存在")

        # 3. 检查可写性
        if not os.access(data_path, os.W_OK):
            print("✗ 数据目录不可写")
            return False

        print("✓ 数据目录可写")

        # 4. 检查配置文件
        if os.path.exists(CONFIG_FILE):
            print(f"✓ 配置文件已存在: {CONFIG_FILE}")
        else:
            print(f"⚠ 配置文件不存在，已创建: {CONFIG_FILE}")

        # 5. 检查数据文件
        print("\n【数据文件检查】")
        existing_files = os.listdir(data_path) if os.path.exists(data_path) else []

        if not existing_files:
            print("⚠ 数据目录为空，需要下载历史数据")
            print("\n  请执行以下操作:")
            print("  1. 运行 signal_app_main.py")
            print("  2. 点击'更新数据'按钮获取最新数据")
            return True

        for fname in REQUIRED_FILES:
            if fname in existing_files:
                fpath = os.path.join(data_path, fname)
                size = os.path.getsize(fpath)
                print(f"✓ {fname} ({size} bytes)")
            else:
                print(f"✗ 缺少: {fname}")

        # 6. 总结
        print("\n【初始化完成】")
        print(f"数据目录: {data_path}")
        print(f"配置文件: {CONFIG_FILE}")
        print("\n初始化成功！您现在可以运行 signal_app_main.py")

        return True

    except Exception as e:
        print(f"\n✗ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_data_files():
    """验证数据文件完整性"""
    print("\n" + "=" * 70)
    print("数据文件完整性检查")
    print("=" * 70 + "\n")

    try:
        data_path = get_data_path()

        if not os.path.exists(data_path):
            print(f"✗ 数据目录不存在: {data_path}")
            return False

        files = os.listdir(data_path)
        print(f"目录: {data_path}")
        print(f"文件数: {len(files)}\n")

        # 检查必需文件
        required_ok = True
        for fname in REQUIRED_FILES:
            if fname in files:
                fpath = os.path.join(data_path, fname)
                size = os.path.getsize(fpath)
                lines = 0
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        lines = sum(1 for _ in f)
                except:
                    pass
                print(f"✓ {fname}")
                print(f"  大小: {size} bytes, 行数: {lines}")
            else:
                print(f"✗ 缺少: {fname}")
                required_ok = False

        # 检查其他文件
        other_files = [f for f in files if not any(f.startswith(prefix) for prefix in ['IF_', '159915_'])]
        if other_files:
            print(f"\n其他文件:")
            for fname in other_files:
                fpath = os.path.join(data_path, fname)
                size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                print(f"  - {fname} ({size} bytes)")

        if required_ok:
            print("\n✓ 所有必需文件完整")
        else:
            print("\n⚠ 缺少必需数据文件")
            print("  请运行程序并点击'更新数据'获取数据")

        return required_ok

    except Exception as e:
        print(f"✗ 检查失败: {e}")
        return False


def reset_config():
    """重置配置文件"""
    print("\n" + "=" * 70)
    print("重置配置文件")
    print("=" * 70 + "\n")

    if not os.path.exists(CONFIG_FILE):
        print("配置文件不存在，无需重置")
        return True

    try:
        # 备份旧配置
        backup_file = CONFIG_FILE + '.bak'
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                old_config = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(old_config)
            print(f"✓ 旧配置已备份: {backup_file}")

        # 删除配置文件
        os.remove(CONFIG_FILE)
        print(f"✓ 已删除配置文件: {CONFIG_FILE}")

        # 重新生成（通过get_data_path）
        data_path = get_data_path()
        print(f"✓ 已生成新配置文件: {CONFIG_FILE}")
        print(f"✓ 数据路径: {data_path}")

        return True

    except Exception as e:
        print(f"✗ 重置失败: {e}")
        return False


def interactive_setup():
    """交互式设置（可选）"""
    print("\n" + "=" * 70)
    print("交互式数据路径设置")
    print("=" * 70 + "\n")

    print("自动检测的数据路径:")
    data_path = get_data_path()
    print(f"  {data_path}\n")

    while True:
        choice = input("是否使用此路径？(y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            print("✓ 已确认使用此路径")
            return True
        elif choice in ['n', 'no']:
            custom_path = input("请输入自定义数据路径: ").strip()
            if custom_path and os.path.exists(custom_path):
                # 保存自定义路径
                try:
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                    config = {
                        'data_path': custom_path,
                        'auto_created': False,
                        'last_verified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'version': '2.0.1'
                    }
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                    print(f"✓ 已保存自定义路径: {custom_path}")
                    return True
                except Exception as e:
                    print(f"✗ 保存失败: {e}")
            else:
                print("✗ 路径不存在或无效")
        elif choice == 'q':
            return False


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序"""
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd == 'diagnose':
            diagnose()
        elif cmd == 'verify':
            verify_data_files()
        elif cmd == 'reset':
            reset_config()
        elif cmd == 'interactive':
            interactive_setup()
        elif cmd == 'help':
            print_help()
        else:
            print(f"未知命令: {cmd}")
            print_help()
    else:
        # 默认：初始化
        init_data_path()


def print_help():
    """打印帮助信息"""
    print("""
IF300 数据路径初始化工具

用法:
  python init_data_path.py                # 检查并初始化数据目录
  python init_data_path.py diagnose       # 诊断路径配置
  python init_data_path.py verify         # 验证数据文件完整性
  python init_data_path.py reset          # 重置配置文件（生成新配置）
  python init_data_path.py interactive    # 交互式设置（选择自定义路径）
  python init_data_path.py help           # 显示此帮助信息

配置文件位置:
  Windows: C:\\Users\\<user>\\.if300\\config.json
  Mac/Linux: ~/.if300/config.json

日志文件位置:
  ~/.if300/if300_paths.log
    """)


if __name__ == '__main__':
    main()
