# Cropping and Border Removal

This is one of NeatReel's core features: detect black borders automatically and keep the useful frame area.

![黑边识别](/黑边识别.png)

### 🤖 Automatic Detection

After import, NeatReel scans video frames and:
1. Samples multiple frames to detect non-content areas
2. Computes a practical crop rectangle automatically
3. Applies the result directly to the preview

This lets you confirm the crop before export instead of discovering a bad border cut afterward.

![主页_预览画面区域](/主页_预览画面区域.png)

### ✂️ Manual Crop Control

If auto-detection is not precise enough, use **Manual Crop**:
- **Visual selection**: drag the crop box directly over the area you want to keep
- **Immediate preview**: see the result while adjusting

::: info Behavior details
The manual crop window always works in the original unrotated frame space, and saved values remain in source-video coordinates. During export, they are normalized into a valid range and aligned to even dimensions.
:::

![手动剪裁画面](/手动剪裁画面.png)

::: tip 💡 Tip
For older videos with unstable dark edges or shadows, manual crop is often the most reliable option.
:::
