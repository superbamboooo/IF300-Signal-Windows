#!/bin/bash
echo "========================================"
echo "多策略交易信号系统 - Mac打包脚本"
echo "========================================"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 安装依赖
echo ""
echo "正在安装依赖..."
pip3 install pandas numpy matplotlib pyinstaller -q

# 打包
echo ""
echo "正在打包..."
pyinstaller --noconfirm --onefile --windowed \
    --name "多策略交易信号系统" \
    --add-data "data_updater.py:." \
    --add-data "weekend_data_updater.py:." \
    --add-data "strategy_if300.py:." \
    --add-data "strategy_weekend.py:." \
    signal_app_main.py

# 复制数据文件夹
echo ""
echo "复制数据文件..."
mkdir -p dist/data
cp -r ../data/* dist/data/ 2>/dev/null || true

echo ""
echo "========================================"
echo "打包完成!"
echo "可执行文件位置: dist/多策略交易信号系统.app"
echo "========================================"
