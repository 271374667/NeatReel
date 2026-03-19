# Export Modes and Hardware Acceleration

NeatReel simplifies encoding choices into four practical modes so you can decide based on speed, file size, and hardware.

![输出质量选择海报](/输出质量选择海报.png)

### 🏃 Speed (SPEED)

- **Use when**: speed matters most
- **Tradeoff**: fastest output, but usually larger files and more aggressive compression choices

### ⚖️ Balanced (BALANCED) - Recommended

- **Use when**: everyday sharing, publishing, or archiving
- **Tradeoff**: balanced defaults for speed, size, and visual quality

### 💎 Quality (QUALITY)

- **Use when**: longer videos, archival output, or material that may be processed again later
- **Tradeoff**: slower, but more conservative about quality and compression efficiency

### 🎮 GPU Hardware Acceleration (GPU)

If you have a supported **NVIDIA GPU** and driver stack, you can enable GPU mode:

- **Current path**: `av1_nvenc`
- **Requirement**: both compatible hardware and working driver support
- **Best for**: high-resolution or high-volume processing where throughput matters

::: danger Important
If your machine does not have a supported NVIDIA GPU or the available driver stack is incomplete, this mode may fail outright.
:::

![输出质量选择](/输出质量选择.png)

## Output Path and Naming

By default, the app creates an `output/` folder under the program root. You can also choose any other folder manually from **Output Folder**.

- **Source run**: the repository root
- **Packaged run**: the same directory as the `exe`

If you choose **Merge into One Video**, the output is a single `.mp4` named with the project ID, for example `a1b2c3d4.mp4`. If you choose **Export Separately**, the app creates a project-ID folder and then writes `0001.mp4`, `0002.mp4`, and so on.

If a cover image is set, the app writes it as an attached cover stream rather than burning it into the video frame. In separate export mode, each output file gets the same cover.

## Processing Page and Progress Feedback

After you click **Start Processing**, `ProcessingService` launches a background worker and pushes state updates to QML:

1. The page shows total progress, current file progress, speed, elapsed time, and estimated remaining time.
2. On success, the state becomes completed; on failure or user abort, it switches to an error-like state.
3. GPU mode uses `av1_nvenc`; other modes currently default to `libx264` with `yuv420p`.
4. When done, **Open Output Folder** opens the destination with Windows Explorer.
