# Development and Build

This section explains how to run **NeatReel** from source, build the Windows package, and work on the documentation site. The project recommends [uv](https://github.com/astral-sh/uv) for Python dependency management.

## 🛠️ Environment

### App

- **Python 3.11+**
- **uv**: used to sync dependencies and run scripts
- **Windows 10/11 64-bit**: the main verified platform

Key dependencies include:

- **PySide6**: GUI and QML integration
- **av (PyAV)**: video reading, encoding, and container output
- **Pillow / numpy / scipy**: preview, image processing, and border detection
- **qthreadwithreturn**: asynchronous thread tasks such as update checks

### Docs Site

If you want to work on `docs/`, you also need:

- **Bun**: to stay aligned with `bun.lock` and CI

## ▶️ Run from Source

1. Sync dependencies:

   ```bash
   uv sync
   ```

2. Compile Qt resources:

   ```bash
   uv run python scripts/compile.py
   ```

3. Start the app:

   ```bash
   uv run python NeatReel.py
   ```

::: warning Default entry behavior
`NeatReel.py` currently defaults to `DEBUG=False`, which means source runs load compiled Qt resources first. If you skip `scripts/compile.py` and do not already have `src/resources/qml_resources.py`, startup may fail immediately.
:::

If you are iterating on the QML UI and want to load local `qml/` files directly, set `DEBUG=True` in `NeatReel.py`.

## 🏗️ Windows Packaging

The repository already includes a build script for packaging a Windows executable:

```bash
uv run python scripts/build.py
```

The script performs these steps automatically:

1. Run `scripts/compile.py` to regenerate `src/resources/qml_resources.qrc` and `src/resources/qml_resources.py`
2. Write the dedicated release launcher `_release_main.py`
3. Use `PyInstaller` to produce the Windows one-dir output

If `PyInstaller` is missing during build, check that your local environment is fully synced.

Build output:

- `dist/NeatReel/`

## 📝 Docs Development

If you change files under `docs/`:

1. Install frontend dependencies:

   ```bash
   bun install --frozen-lockfile
   ```

2. Run a local preview:

   ```bash
   bun run docs:dev
   ```

3. Build the static site:

   ```bash
   bun run docs:build
   ```

4. Preview the built result:

   ```bash
   bun run docs:preview
   ```

## 📂 Directory Overview

- **`NeatReel.py`**: desktop app entry
- **`src/`**: backend logic including preview, reading, merge, and service layers
- **`qml/`**: QML UI code; `qml/Fonts/` and `qml/Images/` are compiled into Qt resources
- **`scripts/`**: resource compilation and PyInstaller build scripts
- **`docs/`**: VitePress documentation site

::: tip 💡 Tip
If you want to change the UI, the most important files are usually under `qml/Windows/`.
:::
