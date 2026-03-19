# Installation and System Requirements

This page answers two practical questions: **Can I use it directly?** and **What environment do I need?**

## For Regular Users

If you only want to use the app, download the latest release here:

<https://github.com/271374667/NeatReel/releases/latest>

Recommended environment:

- **Operating system**: Windows 10 64-bit or Windows 11 64-bit
- **How to run**: download and launch `NeatReel.exe`
- **Default output location**: `output/` under the program root

::: warning Platform note
The current implementation is built around Windows behavior, including single-instance handling and opening the output folder with Explorer. macOS, Linux, and older Windows versions are not official targets.
:::

## GPU Mode Requirements

If you plan to use GPU mode, confirm the following first:

- You are using an **NVIDIA GPU**
- Your GPU and driver support the current encoding path
- If GPU mode fails, switch back to **Speed / Balanced / Quality**

## Source Environment

If you want to run from source or contribute, prepare:

- **Python 3.11+**
- **uv**: the recommended Python dependency manager
- **Bun**: only needed when working on the `docs/` site

You may also want to read:

- [Getting Started](/guide/getting-started)
- [Development and Build](/guide/build)

## Practical Limits

- The app only allows one running instance at a time.
- File extensions are filtered by a whitelist, but successful processing still depends on your local `PyAV / FFmpeg` support for the actual codec combination.
- The app is positioned as a cleanup-and-merge tool, not a full editor with timelines, BGM mixing, or subtitle editing.
