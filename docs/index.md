---
layout: home

hero:
  name: "净影连 / NeatReel"
  text: "去黑边，正朝向，一键拼出好影像"
  tagline: 专为日常视频整理设计的轻量化桌面工具
  image:
    src: /logo.png
    alt: NeatReel Logo
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/introduction
    - theme: alt
      text: 在 GitHub 上查看
      link: https://github.com/271374667/NeatReel

features:
  - icon: ✂️
    title: 智能去黑边
    details: 自动识别视频帧边缘，一键剔除录屏或老旧比例视频的黑色边框，支持手动精准修剪。
  - icon: 🔄
    title: 方向校正与统一
    details: 横竖混拍、倒置视频？统统不是问题。顺逆时针 90° 旋转，一键强制统一横屏或竖屏输出。
  - icon: ⚡
    title: 极速处理模式
    details: 提供速度、均衡、质量三种模式，并支持 NVIDIA GPU 硬件加速，大批量素材瞬间搞定。
  - icon: 🖼️
    title: 实时效果预览
    details: “处理后预览”功能让你在正式导出前即刻看到裁剪与旋转后的成品效果，拒绝盲目等待。
  - icon: 📦
    title: 开箱即用
    details: 界面直观，操作简便。无需复杂的安装配置，拖入视频即可开启高效整理之旅。
  - icon: 🔢
    title: 智能排序
    details: 支持按名称、时间等多种模式自动排序，亦可手动灵活调整，合并顺序尽在掌握。
  - icon: 🎨
    title: 视频封面自定义
    details: 支持为最终合成的视频一键设置个性化封面，让你的作品在分享时更具吸引力。
  - icon: 📤
    title: 多元输出选择
    details: 不仅支持多视频一键合并，更可将处理后的各个片段单独批量输出，满足多样化需求。
---

<div align="center" style="margin-top: 80px; padding: 0 20px;">

## 🎬 什么是净影连？

**净影连 (NeatReel)** 是一款专为视频“整理控”量身打造的开源桌面工具。它并不追求复杂的剪辑功能，而是专注于解决视频合并前最琐碎、最头疼的几个环节：**去除黑边**、**校正方向**、以及**所见即所得的预览**。

![NeatReel Banner](/banner.png)

不论是来自手机的竖拍片段，还是来自录屏带黑边的素材，净影连都能帮你快速归位，一键拼接出清爽干净的完美成片，让您快速带走您需要的视频。

</div>

<div align="center" style="margin-top: 80px; padding: 0 20px;">

## ✂️ 智能算法：一键识别复杂黑边

NeatReel 内置了高效的边缘检测算法，能够自动识别并剔除各种复杂的视频黑边。无论是 4:3 比例在 16:9 屏幕上的填充，还是非标准的录屏边框，只需导入视频，系统便能自动计算出最佳裁剪方案。

![一键识别宣传](/一键识别宣传.png)

告别繁琐的手动计算，让画面回归纯净。

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
