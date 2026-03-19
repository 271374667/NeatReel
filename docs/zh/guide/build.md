# 开发与构建

本章节详细介绍如何从源代码运行、打包 **净影连 / NeatReel**，以及如何构建文档站。项目推荐使用 [uv](https://github.com/astral-sh/uv) 进行 Python 依赖管理。

## 🛠️ 环境依赖

### 应用本体

- **Python 3.11+**
- **uv**：用于同步依赖与执行脚本
- **Windows 10/11 64 位**：当前主要验证平台

主要依赖库包括：

- **PySide6**：提供 GUI 与 QML 集成
- **av (PyAV)**：负责视频读取、编码与容器写入
- **Pillow / numpy / scipy**：参与预览、图像与边界检测流程
- **qthreadwithreturn**：负责异步更新检查等线程任务

### 文档站

如果你需要修改 `docs/` 文档站，还需要准备：

- **Bun**：与仓库中的 `bun.lock` 及 CI 工作流保持一致

## ▶️ 源码运行

1. 同步依赖：

   ```bash
   uv sync
   ```

2. 生成 Qt 资源文件：

   ```bash
   uv run python scripts/compile.py
   ```

3. 启动应用：

   ```bash
   uv run python NeatReel.py
   ```

::: warning 入口默认行为
当前 `NeatReel.py` 默认 `DEBUG=False`，这意味着源码运行时会优先加载编译后的 Qt 资源。如果你跳过 `scripts/compile.py`，并且本地还没有 `src/resources/qml_resources.py`，启动可能直接失败。
:::

如果你在开发 QML 界面，希望直接加载本地 `qml/` 文件，可以手动把 `NeatReel.py` 中的 `DEBUG` 改成 `True`。

## 🏗️ Windows 打包

项目内置了自动化构建脚本，支持快速打包成可执行文件（`.exe`）：

```bash
uv run python scripts/build.py
```

该脚本会自动执行以下步骤：

1. 先调用 `scripts/compile.py` 重新生成 `src/resources/qml_resources.qrc` 与 `src/resources/qml_resources.py`
2. 写入专用的发布入口 `_release_main.py`
3. 通过 `PyInstaller` 生成 Windows one-dir 产物

如果执行打包时提示缺少 `PyInstaller`，请先确认本地已经同步了开发依赖。

打包完成后，输出位于：

- `dist/NeatReel/`

## 📝 文档站开发

如果你修改了 `docs/`：

1. 安装前端依赖：

   ```bash
   bun install --frozen-lockfile
   ```

2. 本地预览：

   ```bash
   bun run docs:dev
   ```

3. 构建静态站点：

   ```bash
   bun run docs:build
   ```

4. 预览构建结果：

   ```bash
   bun run docs:preview
   ```

## 📂 目录结构说明

- **`NeatReel.py`**：桌面应用入口
- **`src/`**：后端核心逻辑，包含预览、读取、合并、服务层等
- **`qml/`**：QML 界面代码，`qml/Fonts/` 与 `qml/Images/` 会被编译进 Qt 资源系统
- **`scripts/`**：资源编译与 PyInstaller 打包脚本
- **`docs/`**：VitePress 文档站

::: tip 💡 提示
如果你想修改界面样式，可以重点关注 `qml/Windows/` 下的各个页面文件。
:::
