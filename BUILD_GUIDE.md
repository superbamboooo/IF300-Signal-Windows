# IF300 MultiStrategy Windows EXE 构建指南

**版本**: 2.0.1
**更新日期**: 2026-02-09
**修复内容**: 数据更新问题已修复，采用更稳定的数据源策略

---

## 📋 概述

本指南指导如何构建新的 Windows EXE 版本。修复内容包括：

- ✅ **数据源优化**: 优先使用 akshare（稳定单源），备选东方财富
- ✅ **路径管理统一**: 所有模块使用统一的 `path_manager` 管理数据路径
- ✅ **持久化配置**: 配置文件保存在 `~/.if300/config.json`
- ✅ **Windows 路径修复**: 修复了 Windows 路径中的转义字符问题

---

## 🚀 快速开始（Windows 本地构建）

### 前置要求

- **Windows 10/11**
- **Python 3.10+** - [下载地址](https://www.python.org/)
- **互联网连接** - 用于下载依赖包

### 构建步骤（仅 3 步！）

#### 1️⃣ 打开命令行

```bash
# 进入 IF300 目录
cd /path/to/newstock/IF300
```

#### 2️⃣ 运行构建脚本

```bash
# 方法 A: 在命令行运行
build_windows.bat

# 方法 B: 在文件浏览器中双击
# 找到 build_windows.bat，双击运行
```

#### 3️⃣ 等待完成

构建过程通常需要 5-15 分钟，脚本会：
- ✓ 检查 Python 环境
- ✓ 安装/检查 PyInstaller
- ✓ 清理旧文件
- ✓ 构建 EXE
- ✓ 复制数据文件
- ✓ 创建压缩包

**完成时会显示**：
```
========================================
[✓] 构建完成！
========================================

输出位置：
  - EXE 目录: dist\MultiStrategy\
  - 可执行文件: dist\MultiStrategy\MultiStrategy.exe
  - 压缩包: dist\MultiStrategy-Windows.zip
```

---

## 📦 输出文件

### 构建成功后的文件结构

```
IF300/
├── dist/
│   └── MultiStrategy/              # ⭐ 最终应用目录
│       ├── MultiStrategy.exe       # 主程序（双击运行）
│       ├── data/                   # 数据文件目录
│       │   ├── IF_主连_季月合约连接_day.csv
│       │   └── 159915_创业板ETF_day.csv
│       ├── path_manager.py
│       ├── init_data_path.py
│       └── ...其他支持文件
│
│   └── MultiStrategy-Windows.zip   # 发布包（可选）
│
└── build/                           # 临时构建文件（可删除）
```

---

## 🧪 测试新版本

### 本地测试

```bash
# 方法 1: 直接运行 EXE
dist\MultiStrategy\MultiStrategy.exe

# 方法 2: 从命令行运行（查看日志）
cd dist\MultiStrategy
MultiStrategy.exe

# 方法 3: 从任意位置创建快捷方式后运行
# 右键 -> 创建快捷方式 -> 放在桌面
```

### 测试清单

- [ ] **应用启动**: EXE 能否正常启动？
- [ ] **加载策略**: 两个策略是否能加载？
  - [ ] IF300 策略
  - [ ] 周末效应策略
- [ ] **历史数据**: 是否能加载历史数据？
- [ ] **更新数据**: 点击"更新数据"是否成功？
  - [ ] 显示成功提示
  - [ ] 数据文件被更新（检查文件时间戳）
- [ ] **路径配置**: 配置文件是否被创建？
  - 位置: `C:\Users\<username>\.if300\config.json`
- [ ] **多次运行**: 重启程序，路径是否保持一致？

---

## 📤 发布

### 方式 1: 直接复制目录（最简单）

```bash
# 将整个 dist\MultiStrategy\ 目录复制给用户
# 用户只需双击 MultiStrategy.exe 即可运行
```

**优点**:
- 最简单，无需任何配置
- 包含所有必要的文件和数据

**缺点**:
- 文件夹较大（~200-300 MB）

### 方式 2: 使用压缩包（推荐）

```bash
# 已自动生成: dist\MultiStrategy-Windows.zip
# 用户下载后解压即可使用
```

**优点**:
- 文件较小（~100-150 MB）
- 便于分发和下载
- 解压后目录结构完整

**缺点**:
- 需要用户手动解压

### 方式 3: GitHub Releases

```bash
# 1. 在 GitHub 上创建 Release
# 2. 上传 dist\MultiStrategy-Windows.zip
# 3. 添加发布说明

版本号: v2.0.1
标题: IF300 MultiStrategy v2.0.1 - 数据更新修复

发布说明:
- ✅ 修复 IF300 数据更新问题
- ✅ 采用更稳定的数据源策略
- ✅ 统一路径管理系统
- ✅ 优先使用 akshare 数据源
```

---

## 🔧 手动构建（高级）

如果 `build_windows.bat` 失败，可以手动执行以下命令：

```bash
# 1. 安装依赖
pip install pyinstaller pandas numpy matplotlib akshare requests

# 2. 进入 IF300 目录
cd IF300

# 3. 构建 EXE
pyinstaller --noconfirm --onedir --windowed ^
  --name "MultiStrategy" ^
  --add-data "path_manager.py;." ^
  --add-data "init_data_path.py;." ^
  --add-data "data_updater.py;." ^
  --add-data "weekend_data_updater.py;." ^
  --add-data "strategy_if300.py;." ^
  --add-data "strategy_weekend.py;." ^
  --add-data "data;data" ^
  signal_app_main.py

# 4. 复制数据文件
xcopy data dist\MultiStrategy\data /E /I /Y

# 5. 最终产物: dist\MultiStrategy\
```

---

## ❓ 常见问题

### Q1: 构建失败，显示"Python not found"

**原因**: Python 未安装或未添加到 PATH

**解决方案**:
```bash
# 检查 Python 是否安装
python --version

# 如果命令不识别，安装 Python:
# https://www.python.org/downloads/
# 安装时勾选 "Add Python to PATH"
```

### Q2: PyInstaller 安装失败

**原因**: pip 配置问题或网络问题

**解决方案**:
```bash
# 更新 pip
python -m pip install --upgrade pip

# 使用清华镜像加速
pip install pyinstaller -i https://mirrors.tsinghua.edu.cn/pypi/web/simple

# 或使用阿里镜像
pip install pyinstaller -i https://mirrors.aliyun.com/pypi/simple/
```

### Q3: 构建后 EXE 无法运行

**排查步骤**:

1. 检查数据文件:
```bash
# data 文件夹应该在 MultiStrategy.exe 同级
dir dist\MultiStrategy\data
```

2. 检查是否有缺少的依赖:
```bash
# 运行诊断
dist\MultiStrategy\MultiStrategy.exe diagnose
```

3. 查看日志:
```bash
# 检查配置文件
type %USERPROFILE%\.if300\config.json

# 检查日志
type %USERPROFILE%\.if300\if300_paths.log
```

### Q4: 数据更新提示成功，但数据没变化

**原因**: 这应该已经在 v2.0.1 中修复了

**验证方法**:
```bash
# 检查是否是新版本
dist\MultiStrategy\MultiStrategy.exe --version

# 应该显示 2.0.1 或更高版本

# 查看数据更新的详细日志
type %USERPROFILE%\.if300\if300_paths.log
```

### Q5: 能否在其他电脑上运行？

**是的**！只需将 `dist\MultiStrategy\` 整个目录复制到其他 Windows 电脑即可。

```
前置要求:
- Windows 10/11
- 无需安装 Python（EXE 已包含运行时）
```

---

## 📊 版本信息

| 组件 | 版本 |
|------|------|
| Python | 3.10+ |
| PyInstaller | 6.0+ |
| pandas | 最新 |
| akshare | 最新 |
| NumPy | 最新 |
| Matplotlib | 最新 |

---

## 🔐 文件完整性检查

构建完成后，验证关键文件是否存在：

```bash
# Windows PowerShell
$files = @(
    "dist\MultiStrategy\MultiStrategy.exe",
    "dist\MultiStrategy\data\IF_主连_季月合约连接_day.csv",
    "dist\MultiStrategy\data\159915_创业板ETF_day.csv",
    "dist\MultiStrategy\path_manager.py",
    "dist\MultiStrategy\init_data_path.py"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "✓ $file"
    } else {
        Write-Host "✗ $file 缺失！"
    }
}
```

---

## 📝 Git 操作

所有代码变更已提交并推送到远程：

```bash
# 最新提交
git log --oneline -5

# 输出：
# 169a03a 添加 IF300 数据更新修复验证报告
# ac3a754 修复 IF300 数据更新问题 - 采用更稳定的策略
```

---

## 🎯 后续优化建议

### 立即可做
- [ ] 测试新版本 EXE
- [ ] 发布到 GitHub Releases
- [ ] 更新用户文档

### 可选优化
- [ ] 添加自动更新检查功能
- [ ] 创建安装程序（.msi）
- [ ] 添加数据源切换界面
- [ ] 实现后台自动数据更新

---

**有任何问题？** 查看日志文件或运行诊断工具：

```bash
dist\MultiStrategy\MultiStrategy.exe diagnose
```

或编辑配置文件：
```
C:\Users\<username>\.if300\config.json
```
