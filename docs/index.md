---
layout: home

hero:
  name: "NeatReel"
  text: "Remove borders, fix orientation, and stitch better videos in one click"
  tagline: A lightweight desktop tool for everyday video cleanup and merging
  image:
    src: /logo.png
    alt: NeatReel Logo
  actions:
    - theme: brand
      text: Getting Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/271374667/NeatReel
    - theme: alt
      text: 中文文档
      link: /zh/

features:
  - icon: ✂️
    title: Smart Border Removal
    details: Detect border areas automatically and remove black bars from mixed footage, with manual crop control when needed.
  - icon: 🔄
    title: Orientation Correction
    details: Normalize mixed landscape and portrait footage with automatic recommendations and one-click 90° rotation controls.
  - icon: ⚡
    title: Multiple Processing Modes
    details: Choose between Speed, Balanced, Quality, and GPU modes based on time, file size, and hardware constraints.
  - icon: 🖼️
    title: Real-time Preview
    details: Preview the processed result before export so you can catch crop or rotation mistakes early.
  - icon: 📦
    title: Easy to Use
    details: Drag in videos, adjust only what matters, and export without a heavy editing workflow.
  - icon: 🔢
    title: Smart Sorting
    details: Use automatic sorting or drag-and-drop ordering to control the final merge sequence.
  - icon: 🎨
    title: Custom Cover Image
    details: Attach a cover image to exported files so finished videos are easier to identify.
  - icon: 📤
    title: Flexible Output
    details: Merge everything into one file or export each cleaned-up segment separately.
---

<div align="center" style="margin-top: 80px; padding: 0 20px;">

## 🎬 What is NeatReel?

**NeatReel** is an open-source desktop tool built for one job: cleaning up and organizing video clips before export. Instead of trying to replace a full editor, it focuses on the steps that usually slow down quick merges: **removing black borders**, **fixing orientation**, and **previewing the result before export**.

![NeatReel Banner](/banner.png)

Whether your clips come from phones, cameras, or recordings with ugly borders, NeatReel helps normalize them and merge them into a cleaner final result.

The current release primarily targets Windows 10/11 64-bit and is designed for clip cleanup, orientation normalization, and crop correction, not full timeline editing or audio production.

</div>

<div align="center" style="margin-top: 80px; padding: 0 20px;">

## ✂️ Smart Detection for Complex Black Borders

NeatReel includes an efficient border-detection workflow that can identify and remove a wide range of black-border patterns. Whether the issue comes from aspect ratio padding, screen recording margins, or inconsistent sources, the app can calculate a practical crop area automatically.

![一键识别宣传](/一键识别宣传.png)

That means less manual trial and error and a much cleaner frame before export.

</div>

<style>
/**
 * 使用 Fluent 2 风格蓝色作为强调色
 */
:root {
  --vp-c-brand-1: #0078d4; 
  --vp-c-brand-2: #005a9e;
  --vp-c-brand-3: #106ebe;
  --vp-c-brand-soft: rgba(0, 120, 212, 0.1);
  
  /* 定义发光背景的变量 */
  --vp-home-hero-image-background-image: radial-gradient(circle, #0078d4 0%, #106ebe 100%);
  --vp-home-hero-image-filter: blur(44px);
}

@media (min-width: 640px) {
  :root {
    --vp-home-hero-image-filter: blur(56px);
  }
}

@media (min-width: 960px) {
  :root {
    --vp-home-hero-image-filter: blur(68px);
  }
}

/**
 * 官方标准的 Logo 发光背景实现
 */
.VPHero .image-container {
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

/* 关键的发光层样式 */
.VPHero .image-bg {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  width: 192px;
  height: 192px;
  background-image: var(--vp-home-hero-image-background-image);
  filter: var(--vp-home-hero-image-filter);
  transform: translate(-50%, -50%);
  opacity: 0.4; /* 初始透明度 */
}

@media (min-width: 640px) {
  .VPHero .image-bg {
    width: 256px;
    height: 256px;
  }
}

@media (min-width: 960px) {
  .VPHero .image-bg {
    width: 320px;
    height: 320px;
  }
}

/**
 * 暗色模式增强
 */
[class~="dark"] .VPHero .image-bg {
  opacity: 0.7;
  --vp-home-hero-image-background-image: radial-gradient(circle, #0078d4 0%, #106ebe 100%);
}

.VPHero .image-container img {
  position: relative;
  z-index: 1; /* 确保 Logo 图片在发光层之上 */
}
</style>
