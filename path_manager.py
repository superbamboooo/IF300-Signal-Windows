#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
IF300 路径管理模块 - 统一数据路径配置和获取
================================================================================

功能：
1. 提供统一的 get_data_path() 函数给所有模块使用
2. 实现持久化配置系统（使用JSON配置文件）
3. 优先级明确的路径查找逻辑
4. 详细的日志输出

配置文件位置：
  Windows: C:\\Users\\<user>\\.if300\\config.json
  Mac/Linux: ~/.if300/config.json

数据路径查找优先级：
  1. 用户配置文件指定的路径（如果存在）
  2. exe同级的 data/ 目录（最可靠）
  3. exe同级的 _internal/data/ 目录（PyInstaller --onefile模式）
  4. 脚本同级的 data/ 目录（开发环境）
  5. 创建默认目录：exe同级或脚本同级的 data/

================================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# ============================================================================
# 配置常量
# ============================================================================

# 配置目录和文件路径
CONFIG_DIR = os.path.expanduser('~/.if300')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# 日志文件路径
LOG_DIR = CONFIG_DIR
LOG_FILE = os.path.join(LOG_DIR, 'if300_paths.log')

# ============================================================================
# 日志配置
# ============================================================================

def _setup_logging():
    """设置日志系统"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            encoding='utf-8'
        )
        # 同时输出到控制台
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('[IF300-PATH] %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    except Exception as e:
        print(f"[警告] 无法设置日志: {e}")


_setup_logging()
logger = logging.getLogger(__name__)

# ============================================================================
# 核心函数
# ============================================================================

def get_data_path():
    """
    获取数据目录路径（统一实现）

    优先级：
    1. 配置文件指定的路径（如果存在且有效）
    2. exe同级data目录（Windows EXE，最可靠）
    3. exe同级_internal/data目录（PyInstaller --onefile模式）
    4. 脚本同级data目录（开发环境）
    5. 上级目录data（开发环境备选）
    6. 自动创建默认目录

    Returns:
        str: 数据目录的绝对路径
    """

    # 1. 尝试从配置文件读取
    saved_path = _load_config_path()
    if saved_path and _is_valid_data_path(saved_path):
        logger.info(f"[路径] 使用配置文件路径: {saved_path}")
        return saved_path

    # 2. 自动检测路径
    detected_path = _detect_data_path()
    if detected_path:
        # 保存到配置
        _save_config_path(detected_path)
        logger.info(f"[路径] 检测到数据目录: {detected_path}")
        return detected_path

    # 3. 创建默认路径
    default_path = _create_default_path()
    _save_config_path(default_path)
    logger.info(f"[路径] 使用默认路径: {default_path}")
    return default_path


def _is_valid_data_path(path):
    """检查路径是否有效"""
    if not path:
        return False
    try:
        return os.path.exists(path) and os.path.isdir(path)
    except Exception:
        return False


def _detect_data_path():
    """
    检测数据路径

    Returns:
        str: 找到的数据目录路径，如果没找到返回 None
    """

    # 区分 Windows EXE 环境和开发环境
    if getattr(sys, 'frozen', False):
        # ========== Windows EXE 环境 ==========
        exe_dir = os.path.dirname(sys.executable)
        logger.info(f"[检测] EXE环境，exe目录: {exe_dir}")

        candidates = [
            os.path.join(exe_dir, 'data'),              # 优先：exe同级
            os.path.join(exe_dir, '_internal', 'data'), # PyInstaller --onefile模式
        ]

        for path in candidates:
            if os.path.exists(path):
                logger.info(f"[检测] 找到数据路径: {path}")
                return path

        logger.info(f"[检测] 未找到现有数据目录，将创建: {candidates[0]}")
        return None

    else:
        # ========== 开发环境 ==========
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)

        logger.info(f"[检测] 开发环境，脚本目录: {script_dir}")

        candidates = [
            os.path.join(script_dir, 'data'),   # 脚本同级（IF300/data）
            os.path.join(parent_dir, 'data'),   # 上级目录（newstock/data）
        ]

        for path in candidates:
            if os.path.exists(path):
                logger.info(f"[检测] 找到数据路径: {path}")
                return path

        logger.info(f"[检测] 未找到现有数据目录，将创建: {candidates[0]}")
        return None


def _load_config_path():
    """
    从配置文件加载路径

    Returns:
        str: 配置中的数据路径，如果不存在或出错返回 None
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                path = config.get('data_path')
                if path:
                    logger.info(f"[配置] 从文件读取路径: {path}")
                    return path
    except Exception as e:
        logger.warning(f"[配置] 读取失败: {e}")

    return None


def _save_config_path(data_path):
    """
    保存路径到配置文件

    Args:
        data_path (str): 要保存的数据路径
    """
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)

        config = {
            'data_path': data_path,
            'auto_created': True,
            'last_verified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '2.0.1'
        }

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        logger.info(f"[配置] 已保存配置文件: {CONFIG_FILE}")
        logger.info(f"[配置] 数据路径: {data_path}")

    except Exception as e:
        logger.error(f"[配置] 保存失败: {e}")


def _create_default_path():
    """
    创建默认数据目录

    Returns:
        str: 创建（或已存在）的目录路径
    """

    # 确定默认路径位置
    if getattr(sys, 'frozen', False):
        # Windows EXE 环境
        base_dir = os.path.dirname(sys.executable)
        default_path = os.path.join(base_dir, 'data')
        logger.info(f"[创建] EXE环境，将创建: {default_path}")
    else:
        # 开发环境
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(script_dir, 'data')
        logger.info(f"[创建] 开发环境，将创建: {default_path}")

    try:
        os.makedirs(default_path, exist_ok=True)
        logger.info(f"[创建] 目录创建成功: {default_path}")
        return default_path

    except Exception as e:
        logger.error(f"[创建] 创建失败: {e}")
        logger.error(f"[创建] 当前工作目录: {os.getcwd()}")

        # 回退到临时目录
        import tempfile
        fallback_path = os.path.join(tempfile.gettempdir(), 'if300_data')
        try:
            os.makedirs(fallback_path, exist_ok=True)
            logger.warning(f"[创建] 回退到临时目录: {fallback_path}")
            return fallback_path
        except Exception as e2:
            logger.critical(f"[创建] 回退失败: {e2}")
            raise


# ============================================================================
# 诊断函数
# ============================================================================

def diagnose():
    """
    诊断数据路径配置

    输出诊断信息用于故障排查
    """
    print("\n" + "=" * 70)
    print("IF300 数据路径诊断信息")
    print("=" * 70)

    # 1. 环境信息
    print(f"\n【环境信息】")
    print(f"  运行环境: {'Windows EXE' if getattr(sys, 'frozen', False) else '开发环境'}")
    print(f"  Python版本: {sys.version}")
    print(f"  工作目录: {os.getcwd()}")

    if getattr(sys, 'frozen', False):
        print(f"  EXE路径: {sys.executable}")
        print(f"  EXE目录: {os.path.dirname(sys.executable)}")

    # 2. 配置文件信息
    print(f"\n【配置文件】")
    print(f"  配置目录: {CONFIG_DIR}")
    print(f"  配置文件: {CONFIG_FILE}")
    print(f"  日志文件: {LOG_FILE}")

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"  配置内容: {json.dumps(config, indent=4, ensure_ascii=False)}")
        except Exception as e:
            print(f"  读取失败: {e}")
    else:
        print(f"  配置文件不存在")

    # 3. 数据路径信息
    print(f"\n【数据路径】")
    try:
        data_path = get_data_path()
        print(f"  当前数据路径: {data_path}")
        print(f"  目录存在: {os.path.exists(data_path)}")
        print(f"  目录可写: {os.access(data_path, os.W_OK)}")

        if os.path.exists(data_path):
            files = os.listdir(data_path)
            print(f"  文件数量: {len(files)}")
            if files:
                print(f"  文件列表:")
                for f in files[:10]:  # 只显示前10个
                    file_path = os.path.join(data_path, f)
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        print(f"    - {f} ({size} bytes)")
                    else:
                        print(f"    - {f}/ (目录)")
                if len(files) > 10:
                    print(f"    ... 还有 {len(files) - 10} 个文件")

    except Exception as e:
        print(f"  错误: {e}")

    # 4. 备选路径检查
    print(f"\n【备选路径检查】")
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        paths_to_check = [
            os.path.join(exe_dir, 'data'),
            os.path.join(exe_dir, '_internal', 'data'),
        ]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        paths_to_check = [
            os.path.join(script_dir, 'data'),
            os.path.join(os.path.dirname(script_dir), 'data'),
        ]

    for path in paths_to_check:
        exists = os.path.exists(path)
        print(f"  {path}: {'✓' if exists else '✗'}")

    print("\n" + "=" * 70 + "\n")


# ============================================================================
# 主程序
# ============================================================================

if __name__ == '__main__':
    print("IF300 路径管理模块")
    print(f"数据路径: {get_data_path()}")
    print(f"配置文件: {CONFIG_FILE}")
    print(f"日志文件: {LOG_FILE}")

    # 可选：运行诊断
    import sys as sys_module
    if len(sys_module.argv) > 1 and sys_module.argv[1] == 'diagnose':
        diagnose()
