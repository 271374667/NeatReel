import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  base: '/NeatReel/',
  title: "净影连 NeatReel",
  description: "去黑边，正朝向，一键拼出好影像",
  themeConfig: {
    logo: '/logo.png',

    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guide/introduction' }
    ],

    sidebar: [
      {
        text: '使用指南',
        items: [
          { text: '项目简介', link: '/guide/introduction' },
          { text: '快速上手', link: '/guide/getting-started' },
        ]
      },
      {
        text: '核心功能',
        items: [
          { text: '画面裁剪与去黑边', link: '/features/crop' },
          { text: '旋转校正', link: '/features/rotation' },
          { text: '实时预览', link: '/features/preview' },
          { text: '输出模式与硬件加速', link: '/features/export' },
          { text: '设置封面', link: '/features/cover' },
          { text: '多种格式支持', link: '/features/formats' },
        ]
      },
      {
        text: '进阶开发',
        items: [
          { text: '开发与构建', link: '/guide/build' },
          { text: '常见问题 FAQ', link: '/guide/faq' }
        ]
      },
      {
        text: '关于我',
        items: [
          { text: '作者的话', link: '/about/author' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/271374667/NeatReel' }
    ],

    footer: {
      message: '基于 LGPL v3 协议发布',
      copyright: 'Copyright © 2026-present PythonImporter'
    }
  }
})
