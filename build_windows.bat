@echo off
chcp 65001
echo ========================================
echo 多策略交易信号系统 - Windows打包脚本
echo ========================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo.
echo 正在安装依赖...
pip install pandas numpy matplotlib pyinstaller -q

REM 打包
echo.
echo 正在打包...
pyinstaller --noconfirm --onefile --windowed ^
    --name "多策略交易信号系统" ^
    --add-data "data_updater.py;." ^
    --add-data "weekend_data_updater.py;." ^
    --add-data "strategy_if300.py;." ^
    --add-data "strategy_weekend.py;." ^
    signal_app_main.py

REM 复制数据文件夹
echo.
echo 复制数据文件...
if not exist "dist\data" mkdir "dist\data"
xcopy /E /I /Y "..\data" "dist\data"

echo.
echo ========================================
echo 打包完成!
echo 可执行文件位置: dist\多策略交易信号系统.exe
echo ========================================
pause
