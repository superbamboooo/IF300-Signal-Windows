@echo off
REM ===========================================================================
REM IF300 MultiStrategy Windows EXE 构建脚本
REM ===========================================================================
REM
REM 使用方式：
REM   1. 在 Windows 命令行中运行: build_windows.bat
REM   2. 或双击运行此文件
REM
REM 前置要求：
REM   - Python 3.10+ 已安装
REM   - pip install pyinstaller pandas numpy matplotlib akshare
REM
REM ===========================================================================

setlocal enabledelayedexpansion

echo ========================================
echo IF300 MultiStrategy Windows EXE 构建器
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装或无法访问
    echo 请从 https://www.python.org/ 下载并安装 Python 3.10+
    pause
    exit /b 1
)

echo [✓] Python 已检测

REM 检查 PyInstaller 是否安装
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo.
    echo [→] 正在安装 PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)

echo [✓] PyInstaller 已检测

REM 检查依赖包
echo.
echo [→] 检查其他依赖...
python -m pip install pandas numpy matplotlib akshare requests -q

echo [✓] 所有依赖已就绪

REM 清理旧的构建文件
echo.
echo [→] 清理旧的构建文件...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
del MultiStrategy.spec >nul 2>&1

echo [✓] 清理完成

REM 构建 EXE
echo.
echo [→] 开始构建 Windows EXE（这可能需要几分钟）...
echo.

pyinstaller --noconfirm --onedir --windowed --name "MultiStrategy" ^
  --add-data "path_manager.py;." ^
  --add-data "init_data_path.py;." ^
  --add-data "data_updater.py;." ^
  --add-data "weekend_data_updater.py;." ^
  --add-data "strategy_if300.py;." ^
  --add-data "strategy_weekend.py;." ^
  --add-data "data;data" ^
  signal_app_main.py

if errorlevel 1 (
    echo.
    echo [错误] EXE 构建失败！
    pause
    exit /b 1
)

echo.
echo [✓] EXE 构建成功！

REM 复制数据文件
echo.
echo [→] 复制数据文件...
if exist data (
    xcopy data dist\MultiStrategy\data /E /I /Y >nul 2>&1
    echo [✓] 数据文件已复制
) else (
    echo [警告] 未找到 data 目录，跳过复制
)

REM 创建发布包
echo.
echo [→] 创建发布压缩包...
cd dist
if exist MultiStrategy-Windows.zip del MultiStrategy-Windows.zip
REM 使用 PowerShell 压缩（更可靠）
powershell -command "Compress-Archive -Path MultiStrategy -DestinationPath MultiStrategy-Windows.zip -Force"
cd ..

if exist dist\MultiStrategy-Windows.zip (
    echo [✓] 发布包已创建
) else (
    echo [警告] 发布包创建失败（这不影响 EXE 使用）
)

REM 显示结果
echo.
echo ========================================
echo [✓] 构建完成！
echo ========================================
echo.
echo 输出位置：
echo   - EXE 目录: dist\MultiStrategy\
echo   - 可执行文件: dist\MultiStrategy\MultiStrategy.exe
echo   - 压缩包: dist\MultiStrategy-Windows.zip（如果创建成功）
echo.
echo 下一步：
echo   1. 测试 EXE: 双击 dist\MultiStrategy\MultiStrategy.exe
echo   2. 发布包: 将 dist\MultiStrategy\ 整个目录打包或复制
echo   3. 更新检查: 确保 data\ 目录在 MultiStrategy.exe 同级
echo.
echo 数据文件夹位置：
echo   dist\MultiStrategy\data\
echo.
echo 配置文件位置：
echo   C:\Users\%%USERNAME%%\.if300\config.json
echo.

pause
