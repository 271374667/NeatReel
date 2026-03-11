# 开发与构建

本章节详细介绍如何从源代码编译 **净影连 / NeatReel** 以及如何进行二次开发。项目推荐使用 [uv](https://github.com/astral-sh/uv) 进行高效的依赖管理。

### 🛠️ 环境依赖

项目基于 Python 3.11+ 开发，主要依赖库包括：
- **PySide6**: 提供现代化 Fluent 风格的 GUI 界面。
- **av (FFmpeg)**: 提供底层的视频帧读取与合并支持。
- **qthreadwithreturn**: 用于处理复杂的异步多线程任务。

### 🏗️ 打包构建

项目内置了自动化构建脚本，支持快速打包成可执行文件（`.exe`）。建议使用 `uv` 来管理虚拟环境和运行构建任务。

1. **准备环境**:
   使用 `uv` 一键同步所有依赖（包含开发依赖）：
   ```bash
   uv sync
   ```

2. **执行资源编译脚本**:
   使用 `uv run` 先重新生成 Qt 资源文件：
   ```bash
   uv run python scripts/compile.py
   ```
   > 该脚本会扫描 `qml/` 目录下的全部前端资源并重建 `src/resources/qml_resources.qrc` 与 `src/resources/qml_resources.py`。`qml/Fonts/AlibabaPuHuiTi-3-55-Regular.ttf` 也会在这一步被写入 RCC，保证调试打包后的字体一致。

3. **执行打包脚本**:
   资源编译完成后，再运行：
   ```bash
   uv run python scripts/build.py
   ```
   > `scripts/build.py` 会先调用 `scripts/compile.py`，然后通过 `PyInstaller` 打包，并把 `src.resources.qml_resources` 一起带入最终产物。

4. **查看结果**:
   打包成功后，可执行文件将出现在根目录下的 `dist` 文件夹内。


### 📂 目录结构说明

- **`src/`**: 后端核心逻辑，包含视频读取器、合并器等。
- **`qml/`**: 前端界面代码，采用 QML 语法编写，`qml/Fonts/` 下的字体会被编译进 Qt 资源系统。
- **`scripts/`**: 项目维护、编译与打包脚本。

::: tip 💡 提示
如果你想修改界面样式，可以重点关注 `qml/Windows/` 下的各个页面文件。
:::
