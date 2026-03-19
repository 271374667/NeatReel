# Troubleshooting and Limits

This page collects common questions and a few current implementation limits you should know in advance.

### Q1: Which systems are supported?

The current release mainly targets **Windows 10 64-bit** and **Windows 11 64-bit**. Single-instance handling and opening the output folder are implemented with Windows behavior in mind.

### Q2: Why can source startup fail even after `uv sync`?

Because `NeatReel.py` currently defaults to `DEBUG=False`, source runs prefer compiled Qt resources. If `src/resources/qml_resources.py` does not exist yet, run:

```bash
uv run python scripts/compile.py
uv run python NeatReel.py
```

If you want to debug directly against local `qml/` files, set `DEBUG=True` manually.

### Q3: Why does GPU mode fail on my machine?

GPU mode currently uses **NVIDIA `av1_nvenc`**. If your GPU model, driver, or hardware encoding capability is not sufficient, processing may fail. In that case, switch back to **Speed / Balanced / Quality**.

### Q4: Why do some videos fail to import or process?

The UI currently allows these common extensions:

`mp4`、`mkv`、`mov`、`avi`、`webm`、`flv`、`wmv`、`m4v`、`mpg`、`mpeg`、`3gp`、`3g2`、`f4v`、`rm`、`rmvb`、`asf`

But matching the extension whitelist does not guarantee successful processing. The final result still depends on whether your local `PyAV / FFmpeg` stack supports the actual internal codec combination.

### Q5: Where is the default output folder?

The default output directory is always named `output/`, but its location depends on how the app is launched:

- **Source run**: repository root
- **Packaged run**: the same directory as the `exe`

Output naming:

- **Merge into one video**: an `.mp4` named with an 8-character project ID
- **Export separately**: a folder named with an 8-character project ID containing `0001.mp4`, `0002.mp4`, and so on

### Q6: What if auto border removal is not accurate enough?

Recommended order:

1. Click **Use Original Video** and compare the automatic result with the source.
2. If it still looks wrong, open **Manual Crop**.
3. Manual crop works in original unrotated coordinates and is normalized on export.

### Q7: Why can't I open two app windows at the same time?

That is by design. The app only allows a single running instance and will bring the existing window to the front instead of starting another one.

### Q8: Can I add BGM when merging?

No. **NeatReel** is positioned as a cleanup-and-merge tool rather than a full nonlinear editor. It does not currently support multi-track editing, external BGM, or subtitle timelines.

![输出完成](/输出完成.png)
