![banner](/banner.png)

---

# Introduction

**NeatReel** is an open-source desktop tool for people who mainly need to clean up and combine videos. It does not try to be a full editor. Instead, it focuses on the annoying steps that happen before merging: **removing black borders**, **fixing orientation**, and **previewing the output before export**.

When video clips come from different devices or recording methods, they often have mixed orientation, inconsistent borders, and mismatched presentation. NeatReel helps normalize them quickly and then export them in a cleaner form. It offers Speed, Balanced, Quality, and GPU modes, but all of them are re-encoding paths rather than lossless passthrough.

![主页预览](/主页_鼠标拖拽排序.png)

::: tip Scope
The current release mainly targets Windows 10 64-bit and Windows 11 64-bit. It is a cleanup-and-merge tool, not a full nonlinear editor with timeline editing, BGM mixing, or subtitle authoring.
:::

### 💡 Why use it?

These are the common pain points it tries to reduce:

1. **Black borders**: recorded or archived footage often includes visible bars that look bad after merging.
2. **Mixed orientation**: portrait phone clips and landscape camera clips do not line up cleanly by default.
3. **Too much trial and error**: finding a mistake after export wastes time.
4. **Overkill tools**: many users just want to clean and combine clips without opening a heavyweight editor.

NeatReel brings the high-frequency steps into one desktop interface so you can fix issues before export instead of after.

### ✨ Core Design Ideas

- **Border removal**: detect and crop distracting black bars automatically, with manual correction when needed.
- **Orientation correction**: recommend a direction automatically, then let you override clip rotation manually.
- **Preview before export**: confirm cropping and rotation before waiting for the final render.
- **One-click output**: merge into one video or export cleaned-up clips separately.
