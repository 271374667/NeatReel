# Getting Started: From Import to Export

Before you start, make sure you have either downloaded the release build or prepared the source environment described in the development guide.

Latest download: <https://github.com/271374667/NeatReel/releases/latest>

## Step 1: Import Videos

You can import clips in two ways:

- **Drag and drop (recommended)**: drag multiple files into the list on the left.
- **File picker**: click the **Add Videos** button in the list area.

::: tip Note
The current UI accepts video files directly. It does not expand folders automatically, so dropped folders will be ignored.
:::

Common supported extensions:

`mp4`、`mkv`、`mov`、`avi`、`webm`、`flv`、`wmv`、`m4v`、`mpg`、`mpeg`、`3gp`、`3g2`、`f4v`、`rm`、`rmvb`、`asf`

![主页拖放视频](/主页_拖放视频.webp)

## Step 2: Organize Order

After import, the list order becomes the processing order. You can adjust it in several ways:

- **Right-click smart sorting**: useful for numbered, date-like, or Windows-style renamed files.
- **Manual drag sorting**: press and hold an item, then drag it up or down.
- **Multi-select and delete**:
  - `Ctrl + A`：全选
  - `Ctrl + D`、`Delete`、`Backspace`：删除选中项
  - `Ctrl + 鼠标左键`：单个增减选中
  - `Shift + 鼠标左键`：连续范围选择

## Step 3: Preview, Rotate, and Remove Borders

After you select a video, the right side shows its processed preview.

1. **Preview the processed result**: by default, the preview reflects border removal and orientation correction.
2. **Switch back to the original**: use **Use Original Video** to compare the automatic result with the source.
3. **Rotate manually**: if orientation is wrong, use the clockwise or counterclockwise 90° buttons.

::: info Auto-rotation rule
If a clip has not been rotated manually, the app can recommend `0°` or `90°` based on the chosen output orientation. Once you rotate a clip manually, your own `0/90/180/270` value takes priority.
:::

![主页_旋转视频](/主页_旋转视频.webp)

## Step 4: Use Manual Crop When Needed

If the automatic crop is not good enough, open **Manual Crop**:

1. Click **Manual Crop**.
2. Drag the crop frame in the popup window.
3. Confirm the crop and apply it back to the current video item.

::: tip Actual behavior
The manual crop page always works on the original unrotated frame and stores crop coordinates in source-video space. On export, they are normalized to a valid range and aligned to even dimensions.
:::

![手动剪裁页面](/手动剪裁页面.webp)

## Step 5: Configure Output

The **Output Settings** panel contains four key areas:

1. **Orientation**: choose a unified landscape or portrait output.
2. **Output mode**:
   - `Merge into One Video`
   - `Export Separately`
3. **Advanced settings**:
   - `Processing Mode`: Speed, Balanced, Quality, GPU
   - `Enable Auto Crop`: affects current items and future imports
4. **Extras**:
   - `Video Cover`: attach an image as a cover stream
   - `Output Folder`: defaults to `output/` under the program root

![主页_高级设置和输出](/主页_高级设置和输出.webp)

## Step 6: Start Processing and Check Results

After clicking **Start Processing**, the app opens the processing page:

- It shows total progress, current file progress, speed, elapsed time, and estimated remaining time.
- You can abort while processing.
- When finished, you can open the output folder directly.

Output naming:

- **Merge mode**: one `.mp4` file named with an 8-character project ID, for example `a1b2c3d4.mp4`
- **Separate mode**: one folder named with an 8-character project ID, then `0001.mp4`, `0002.mp4`, and so on

![输出完成](/输出完成.png)
