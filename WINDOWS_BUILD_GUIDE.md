# Windows 版本构建指南

## 构建方法

从本版本开始，**Windows EXE 版本通过 GitHub Actions 自动构建**，无需本地打包。

### 自动构建流程

```
提交代码到 GitHub main 分支
         ↓
GitHub Actions 自动检测
         ↓
在 Windows 环境构建 EXE
         ↓
上传到 Artifacts（保留 30 天）
         ↓
下载使用
```

---

## 获取最新的 Windows EXE

### 方法 1：通过 GitHub Web 界面（推荐）

1. **进入项目 Actions 页面**
   - 点击 GitHub 项目的 `Actions` 标签
   - 在左侧菜单找到 `Build Windows EXE`

2. **选择最新的构建**
   - 点击列表中最新的工作流运行
   - 确保状态是 ✓ 绿色（成功）

3. **下载 EXE**
   - 向下滚动到 `Artifacts` 部分
   - 点击 `IF300-Signal-Windows` 下载
   - 解压后得到 `MultiStrategy.exe`

### 方法 2：通过命令行（快速）

```bash
# 获取最新的运行 ID
gh run list --workflow="build.yml" --limit 1 --json "databaseId" --jq ".[0].databaseId"

# 下载 EXE（假设 ID 是 21362037661）
gh run download 21362037661 -n "IF300-Signal-Windows" -D "./windows-exe"

# 查看下载的文件
ls -lh windows-exe/
```

---

## 什么时候会触发构建？

以下情况会自动触发新的构建：

✓ **代码提交到 main 分支**
- 包括策略文件修改
- 包括 GUI 界面修改
- 包括数据更新模块修改

✓ **手动触发**
- 在 GitHub Actions 页面点击 `Run workflow`
- 选择 `Build Windows EXE`
- 点击 `Run workflow` 按钮

✓ **Pull Request**
- 提交 PR 到 main 分支时也会自动构建

---

## 构建信息

### 构建配置
- **操作系统**: Windows Server Latest
- **Python 版本**: 3.10
- **输出**: `MultiStrategy.exe`（单文件可执行程序）
- **打包工具**: PyInstaller
- **包含模块**:
  - `signal_app_main.py`（主程序）
  - `strategy_if300.py`（IF300 策略）
  - `strategy_weekend.py`（创业板策略）
  - `data_updater.py`（数据更新）

### Artifacts 保留期
- 默认保留 30 天
- 过期后自动删除
- 若需长期保存，下载后妥善保管

---

## 构建失败排查

如果构建失败（红色 ✗ 标记），可能的原因：

| 原因 | 解决方案 |
|------|---------|
| Python 依赖安装失败 | 检查 GitHub Actions 日志，通常是临时网络问题，稍后重试 |
| 代码语法错误 | 检查最新提交的代码，修复错误后重新提交 |
| PyInstaller 打包错误 | 检查是否有新增的模块未正确引入 |
| 磁盘空间不足 | GitHub Actions 环境有限制，通常不会发生 |

查看构建日志：
1. 点击失败的工作流运行
2. 点击 `Build Windows EXE` 步骤
3. 查看详细错误信息

---

## 本地开发测试

如果需要在本地测试 EXE 打包，可以使用 macOS 构建脚本：

```bash
./build_mac.sh
```

这会生成 `dist/多策略交易信号系统.app`（macOS 应用程序）

---

## 清理本地构建文件

如果需要清理本地的构建产物：

```bash
# 删除旧的构建文件
rm -rf build/ dist/ *.spec

# 保持干净的工作区
git clean -fd
```

---

## 常见问题

### Q1: 为什么不再提供 build_windows.bat？

**A:** 本地打包容易出现环境问题（依赖版本差异、路径问题等）。GitHub Actions 提供标准化的 Windows 环境，保证构建成功率和一致性。

### Q2: EXE 可以直接在 Windows 上运行吗？

**A:** 是的！`MultiStrategy.exe` 是完整的可执行程序，包含了所有必要的 Python 依赖，无需安装 Python。

### Q3: 如何确保下载的 EXE 是最新的？

**A:** 查看 Artifacts 旁的时间戳，应该是你最后一次提交代码的时间。或者在 GitHub 工作流中查看构建对应的 commit message。

### Q4: 可以修改 EXE 的名称吗？

**A:** 可以。`MultiStrategy.exe` 只是打包时的名称，可以重命名为任意名称使用。不会影响功能。

---

## 工作流文件位置

GitHub Actions 工作流配置文件：
```
.github/workflows/build.yml
```

如需修改构建配置（如 Python 版本、依赖包等），编辑此文件后提交即可。

