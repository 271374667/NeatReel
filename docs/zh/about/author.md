---
aside: false
---

# 作者的啰嗦

感谢您使用 **净影连 (NeatReel)**！

这个项目最初源于我对视频处理工具的一个简单想法：我其实并不需要像 PR、达芬奇那样复杂的软件，我只是有一堆短视频需要拼接，拼好之后才方便观看。能不能有一款工具，不需要复杂的剪辑流程，就能帮我处理掉那些讨厌的黑边，并把各种拍摄方向的视频统一起来？

**净影连 (NeatReel)** 是我之前 VideoFusion 的复活项目，一开始写 VideoFusion 的时候，我的技术还不是很成熟，但又想做一款包含很多功能的视频处理工具，结果坑挖得太大，最终只能弃坑。

我吸取了教训，这次的软件只关注重点功能，优先聚焦于视频去黑边和画面旋转，并优化了处理速度，确保工具有很高的可用性，能真正落地，而不再一开始就追求“大而全”。

其中的核心去黑边算法依然是我自己调优的自研算法。虽然让 AI 写了多个版本，但最终效果都不如我自己写的，在性能或表现上总有不达标的地方。使用了 VideoFusion 核心算法的 NeatReel，也算是让这个项目重新复活了。另外，如果有朋友对这个算法感兴趣，它们位于 [变化区域去黑边](https://github.com/271374667/VideoFusion/blob/master/src/common/black_remove_algorithm/video_remover.py) 和 [孤岛去黑边](https://github.com/271374667/VideoFusion/blob/master/src/common/black_remove_algorithm/img_black_remover.py)，欢迎大家研究交流。虽然一开始用了很多方法，像是霍夫变换、像素变化边界检测等等，在此期间，我甚至还拜托朋友收集了两千多张图片，准备拿来训练 Yolo（PS：虽然最后大部分都没用上）。但最终还是用了老算法，果然姜还是老的辣。另外，在这里要重点感谢一下帮我收集图片的朋友，愿您在学习和生活中事事顺利，心想事成，同时再次感谢您为开源事业做出的贡献！

# 软件的名字

软件名字的灵感来自镜音双子里面的镜音连，因为本人也算是半个MMD爱好者(bushi)，最后本来想放在封面上面，但是 AI 怎么生成都不是很美观，最后放弃，下面是镜音双子的立绘，不知道6202年了，还有没有人入坑MMD。

净影连中，净表示能够将黑边处理干净，影表示支持多种影片格式，连则是软件的功能，这个软件的最初的功能便是连接视频，使用净影连让您的影片片段干净的连接!

<div style="text-align:center;">

![镜音双子](/镜音双子.webp)

</div>

<div class="team-section">
  <h2 class="section-title">开发者</h2>
  <div class="team-container">
    <div class="member-card">
      <DocImage src="/author.png" alt="PythonImporter" variant="avatar" class="member-avatar"></DocImage>
      <div class="member-name">PythonImporter</div>
      <div class="member-title">NeatReel 开发者</div>
      <div class="member-links">
        <a href="https://github.com/271374667" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>
  </div>

  <h2 class="section-title">特别感谢</h2>
  <div class="team-container">
    <div class="member-card">
      <DocImage src="/contributor_avatar.jpg" alt="陈x漩" variant="avatar" class="member-avatar"></DocImage>
      <div class="member-name">陈x漩</div>
      <div class="member-title">热心支持者 / 图像收集者</div>
      <p class="member-desc">在项目初期提供了大量的图像样本，协助了去黑边算法的调研工作。</p>
    </div>
  </div>
</div>

<style scoped>
.team-section {
  margin-top: 4rem;
  border-top: 1px solid var(--vp-c-divider);
  padding-top: 2rem;
}
.section-title {
  text-align: center;
  margin-bottom: 2rem !important;
  border-bottom: none !important;
  font-weight: 600;
}
.team-container {
  display: flex;
  justify-content: center;
  gap: 2rem;
  flex-wrap: wrap;
  margin-bottom: 4rem;
}
.member-card {
  background-color: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 2rem;
  width: 100%;
  max-width: 300px;
  text-align: center;
  transition: all 0.3s ease;
}
.member-card:hover {
  border-color: var(--vp-c-brand);
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.member-avatar {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  margin: 0 auto 1.25rem;
  object-fit: cover;
  background-color: var(--vp-c-bg-mute);
}
.member-name {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 0.5rem;
}
.member-title {
  font-size: 0.9rem;
  color: var(--vp-c-brand);
  font-weight: 500;
  margin-bottom: 1rem;
}
.member-desc {
  font-size: 0.85rem;
  color: var(--vp-c-text-2);
  line-height: 1.6;
  text-align: left;
}
.member-links a {
  font-size: 0.9rem;
  color: var(--vp-c-brand);
  text-decoration: none;
}
.member-links a:hover {
  text-decoration: underline;
}
</style>
