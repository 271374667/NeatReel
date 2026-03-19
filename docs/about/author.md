---
aside: false
---

# Author's Note

Thanks for using **NeatReel**.

This project started from a simple need: I did not need a huge editor like Premiere or DaVinci. I just had a lot of short clips that needed to be cleaned up and stitched together so they were easier to watch. I wanted something that could remove annoying black borders and normalize mixed orientations without forcing me through a full editing workflow.

**NeatReel** is effectively a revival of an older project of mine, VideoFusion. When I first wrote VideoFusion, I was not mature enough technically and tried to build too much at once. The scope became too large, and the project stalled.

This time I kept the scope focused. The software concentrates on border removal, rotation correction, and a practical workflow that is actually usable instead of chasing a giant feature list.

The core border-removal algorithm is still my own tuned implementation. I experimented with multiple approaches, including AI-generated variants and other detection methods, but in the end the old hand-tuned algorithm still performed better in the ways that mattered. In that sense, NeatReel also brought the most useful part of VideoFusion back to life.

If you are curious about the earlier algorithm work, you can still find the old implementations here:

- [Motion-region border removal](https://github.com/271374667/VideoFusion/blob/master/src/common/black_remove_algorithm/video_remover.py)
- [Island-based border removal](https://github.com/271374667/VideoFusion/blob/master/src/common/black_remove_algorithm/img_black_remover.py)

During that period I also tried a lot of other ideas, including Hough transforms, boundary detection from pixel changes, and even collecting thousands of image samples for possible model training. Most of that did not survive into the final tool, but the exploration was still valuable. I also want to thank the friend who helped collect those samples and supported the project.

# About the Name

The name was inspired partly by "Len" from Kagamine Len and Rin. I am also an MMD fan, although that influence ended up staying mostly in spirit rather than in the UI. The Chinese name "净影连" roughly carries three ideas: clean visuals, support for video material, and connecting clips together.

<div style="text-align:center;">

![镜音双子](/镜音双子.webp)

</div>

<div class="team-section">
  <h2 class="section-title">Developer</h2>
  <div class="team-container">
    <div class="member-card">
      <DocImage src="/author.png" alt="PythonImporter" variant="avatar" class="member-avatar"></DocImage>
      <div class="member-name">PythonImporter</div>
      <div class="member-title">NeatReel Developer</div>
      <div class="member-links">
        <a href="https://github.com/271374667" target="_blank" rel="noopener">GitHub</a>
      </div>
    </div>
  </div>

  <h2 class="section-title">Special Thanks</h2>
  <div class="team-container">
    <div class="member-card">
      <DocImage src="/contributor_avatar.jpg" alt="陈x漩" variant="avatar" class="member-avatar"></DocImage>
      <div class="member-name">陈x漩</div>
      <div class="member-title">Supporter / Image Contributor</div>
      <p class="member-desc">Provided a large number of image samples during the early research phase of the border-removal algorithm.</p>
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
