# Import, Sorting, and Export Workflow

This page connects the main interface actions into one practical workflow and is useful once the app is already installed.

## 1. Import Files

The list on the left is the starting point. It supports:

- Dragging multiple video files into the list
- Clicking **Add Videos** and selecting files manually

当前界面接受的是视频文件本身，不会自动展开文件夹。支持的常见扩展名包括：

`mp4`、`mkv`、`mov`、`avi`、`webm`、`flv`、`wmv`、`m4v`、`mpg`、`mpeg`、`3gp`、`3g2`、`f4v`、`rm`、`rmvb`、`asf`

::: tip Note
The current import flow does not deduplicate files. If you add the same file multiple times, it will appear multiple times in the list.
:::

## 2. Sorting and Batch Actions

After import, the list order becomes the processing order. You can adjust it like this:

- **Smart Ascending / Smart Descending**: useful when filenames already contain sequence information
- **Manual drag sorting**: press and hold an item, then drag
- **Move to Top / Move to Bottom**
- **Delete**: remove one item or multiple selected items

Batch selection shortcuts:

- `Ctrl + A`：全选
- `Ctrl + D`、`Delete`、`Backspace`：删除选中项
- `Ctrl + 鼠标左键`：增减单个选中
- `Shift + 鼠标左键`：连续选中范围

The smart sort logic roughly works like this:

- Pure numeric names sort numerically
- Windows rename style names like `File (12)` sort by the number in parentheses
- Date-like names sort by date
- Everything else falls back to normal string sorting

## 3. Preview and Per-file Adjustments

After selecting a clip, the **Video Details** section shows its current processed result.

You can do four important things here:

1. Preview the result
2. Switch between the original and the processed view
3. Rotate 90° clockwise or counterclockwise
4. Open the manual crop window

Important behavior details:

- Auto-rotation only applies to clips you have not rotated manually
- Auto-rotation only recommends `0°` or `90°`
- Manual crop works in original unrotated frame coordinates
- Confirming manual crop re-enables crop handling for the current item and normalizes the stored area on export

## 4. Global Output Settings

The lower-right **Output Settings** panel controls how the whole job is exported.

### Orientation

- **Landscape**
- **Portrait**

This affects both auto-rotation recommendations and the final output direction.

### Output Mode

- **Merge into One Video**: combine all clips into one file
- **Export Separately**: export each cleaned-up clip individually

Naming rules:

- Merge mode: one `.mp4` file named with an 8-character project ID
- Separate mode: one folder named with an 8-character project ID containing `0001.mp4`, `0002.mp4`, and so on

### Advanced Settings

- **Processing Mode**: Speed, Balanced, Quality, GPU
- **Enable Auto Crop**: affects both current items and future imported items
- **Video Cover**: writes an attached cover image into the exported file
- **Output Folder**: defaults to `output/` under the program root

## 5. Processing Page and Results

After clicking **Start Processing**, the processing page shows:

- Total progress
- Current file progress
- Processing speed
- Elapsed time
- Estimated remaining time
- Current status

You can abort while processing. When the task finishes, you can go back or open the output folder directly.

::: warning Windows behavior
The **Open Output Folder** action currently uses `Explorer`, which is one reason the current release is primarily designed around Windows.
:::
