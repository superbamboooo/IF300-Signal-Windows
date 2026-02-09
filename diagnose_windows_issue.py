#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Windows 版本诊断脚本
================================================================================
诊断数据更新问题，找出根本原因
"""

import sys
import os
import platform


def print_header(text):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_section(text):
    """打印小标题"""
    print(f"\n{'─' * 80}")
    print(f"► {text}")
    print(f"{'─' * 80}")


def diagnose_environment():
    """诊断运行环境"""
    print_section("1. 运行环境诊断")

    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print(f"Python可执行文件: {sys.executable}")
    print(f"是否打包后: {'是 (sys.frozen=True)' if getattr(sys, 'frozen', False) else '否 (开发环境)'}")
    print(f"当前工作目录: {os.getcwd()}")


def diagnose_file_structure():
    """诊断文件结构"""
    print_section("2. 文件结构诊断")

    # 当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"脚本目录: {script_dir}")

    # 检查关键文件
    files_to_check = [
        ('data_updater.py', script_dir),
        ('strategy_if300.py', script_dir),
        ('strategy_weekend.py', script_dir),
        ('data', script_dir),
    ]

    print("\n关键文件/文件夹检查:")
    for name, path in files_to_check:
        full_path = os.path.join(path, name)
        exists = os.path.exists(full_path)
        status = "✓ 存在" if exists else "✗ 不存在"

        if os.path.isdir(full_path):
            size_info = f" ({len(os.listdir(full_path))} 项)"
            status += size_info
        elif exists:
            size = os.path.getsize(full_path)
            size_kb = size / 1024
            status += f" ({size_kb:.1f} KB)"

        print(f"  {status:20} {full_path}")


def diagnose_data_files():
    """诊断数据文件"""
    print_section("3. 数据文件诊断")

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    if not os.path.exists(data_dir):
        print(f"✗ data 目录不存在: {data_dir}")
        return

    print(f"✓ data 目录存在: {data_dir}")
    print(f"  目录大小: {get_dir_size(data_dir) / 1024 / 1024:.1f} MB")

    # 列出data目录中的文件
    files = os.listdir(data_dir)
    print(f"\n数据文件列表 ({len(files)} 个):")

    for filename in sorted(files):
        filepath = os.path.join(data_dir, filename)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            size_mb = size / 1024 / 1024
            status = "✓" if size > 0 else "✗ (文件为空)"
            print(f"  {status} {filename:40} {size_mb:8.2f} MB")


def diagnose_data_path_logic():
    """诊断数据路径逻辑"""
    print_section("4. 数据路径查找逻辑")

    print("模拟 get_data_path() 函数的查找过程:\n")

    # 模拟打包和非打包环境
    is_frozen = getattr(sys, 'frozen', False)
    exe_dir = os.path.dirname(sys.executable)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if is_frozen:
        print(f"检测到: 打包后运行 (sys.frozen=True)")
        print(f"EXE 目录: {exe_dir}")

        possible_paths = [
            os.path.join(exe_dir, '_internal', 'data'),
            os.path.join(exe_dir, 'data'),
            os.path.join(os.path.dirname(exe_dir), 'data'),
            os.path.join(os.getcwd(), 'data'),
        ]

        print("\n尝试以下路径:")
        for i, path in enumerate(possible_paths, 1):
            exists = os.path.exists(path)
            status = "✓ 找到" if exists else "✗ 未找到"
            print(f"  {i}. {status} {path}")

    else:
        print(f"检测到: 开发环境 (sys.frozen=False)")
        print(f"脚本目录: {script_dir}")

        possible_paths = [
            os.path.join(script_dir, 'data'),
            os.path.join(os.path.dirname(script_dir), 'data'),
        ]

        print("\n尝试以下路径:")
        for i, path in enumerate(possible_paths, 1):
            exists = os.path.exists(path)
            status = "✓ 找到" if exists else "✗ 未找到"
            print(f"  {i}. {status} {path}")


def diagnose_permissions():
    """诊断文件权限"""
    print_section("5. 文件权限诊断")

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    if not os.path.exists(data_dir):
        print(f"✗ data 目录不存在，无法检查权限")
        return

    # 检查读权限
    can_read = os.access(data_dir, os.R_OK)
    can_write = os.access(data_dir, os.W_OK)
    can_execute = os.access(data_dir, os.X_OK)

    print(f"data 目录权限检查:")
    print(f"  {'✓' if can_read else '✗'} 可读取")
    print(f"  {'✓' if can_write else '✗'} 可写入")
    print(f"  {'✓' if can_execute else '✗'} 可执行")

    if not can_write:
        print(f"\n⚠️ 警告: 无法写入 data 目录")
        print(f"   原因: 可能是权限限制")
        print(f"   解决: 将应用移到非系统保护目录（如 Desktop），或以管理员身份运行")


def diagnose_imports():
    """诊断必要模块"""
    print_section("6. 依赖模块诊断")

    modules = ['pandas', 'numpy', 'matplotlib', 'requests', 'tkinter']

    print("检查依赖模块:")
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module:20} 可用")
        except ImportError:
            print(f"  ✗ {module:20} 未安装")


def diagnose_network():
    """诊断网络连接"""
    print_section("7. 网络连接诊断")

    import urllib.request
    import urllib.error

    urls = [
        ('新浪财经', 'https://finance.sina.com.cn'),
        ('东方财富', 'https://www.eastmoney.com'),
        ('和讯期货', 'https://futures.hexun.com'),
    ]

    print("测试网络连接:")
    for name, url in urls:
        try:
            response = urllib.request.urlopen(url, timeout=3)
            status = f"✓ 可连接 (HTTP {response.status})"
        except urllib.error.URLError as e:
            status = f"✗ 无法连接 ({str(e)[:40]}...)"
        except Exception as e:
            status = f"✗ 错误 ({str(e)[:40]}...)"

        print(f"  {status:50} {name}")


def get_dir_size(path):
    """计算目录大小"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total


def print_summary():
    """打印总结"""
    print_section("诊断总结")

    print("""
✅ 如果上面的诊断显示:
  - data 目录存在且包含 CSV 文件
  - 有读写权限
  - 网络连接正常

  那么数据更新应该可以正常工作！

❌ 如果发现问题，按以下顺序尝试修复:

  1. 如果 data 目录不存在或文件为空
     → 重新下载最新的 Windows 版本（包含完整的 data 文件夹）

  2. 如果权限有问题
     → 将应用移到用户目录（如 Desktop）
     → 或以管理员身份运行

  3. 如果网络无法连接
     → 检查防火墙设置
     → 检查代理设置
     → 尝试连接其他网站确保网络正常

  4. 如果依赖模块缺失
     → 重新安装 Python
     → 重新下载 Windows EXE 版本（自带所有依赖）

📞 仍有问题？
   - 检查本地日志输出
   - 查看 WINDOWS_USAGE_FIX.md 获取更多帮助
""")


def main():
    print_header("Windows 版本诊断工具")
    print("此工具将诊断数据更新问题的根本原因\n")

    try:
        diagnose_environment()
        diagnose_file_structure()
        diagnose_data_files()
        diagnose_data_path_logic()
        diagnose_permissions()
        diagnose_imports()
        diagnose_network()
        print_summary()

    except Exception as e:
        print(f"\n✗ 诊断过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("诊断完成！")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
