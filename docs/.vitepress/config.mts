import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'

type ImageMeta = {
  width: number
  height: number
}

const configDir = path.dirname(fileURLToPath(import.meta.url))
const docsDir = path.dirname(configDir)
const publicDir = path.join(docsDir, 'public')
const imageMetaMap = collectImageMeta(publicDir)

function collectImageMeta(rootDir: string) {
  const metaMap: Record<string, ImageMeta> = {}

  if (!fs.existsSync(rootDir)) {
    return metaMap
  }

  const walk = (currentDir: string) => {
    for (const entry of fs.readdirSync(currentDir, { withFileTypes: true })) {
      const fullPath = path.join(currentDir, entry.name)

      if (entry.isDirectory()) {
        walk(fullPath)
        continue
      }

      const buffer = fs.readFileSync(fullPath)
      const meta = readImageMeta(buffer)

      if (!meta) {
        continue
      }

      const publicPath = `/${path.relative(rootDir, fullPath).split(path.sep).join('/')}`
      metaMap[publicPath] = meta
    }
  }

  walk(rootDir)

  return metaMap
}

function readImageMeta(buffer: Buffer) {
  return readPngMeta(buffer) ?? readJpegMeta(buffer) ?? readWebpMeta(buffer)
}

function readPngMeta(buffer: Buffer) {
  const pngSignature = '89504e470d0a1a0a'

  if (buffer.length < 24 || buffer.subarray(0, 8).toString('hex') !== pngSignature) {
    return null
  }

  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  }
}

function readJpegMeta(buffer: Buffer) {
  if (buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) {
    return null
  }

  let offset = 2

  while (offset + 9 < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1
      continue
    }

    let marker = buffer[offset + 1]
    offset += 2

    while (marker === 0xff && offset < buffer.length) {
      marker = buffer[offset]
      offset += 1
    }

    if (marker === 0xd8 || marker === 0x01) {
      continue
    }

    if (marker === 0xd9 || marker === 0xda) {
      break
    }

    if (offset + 2 > buffer.length) {
      break
    }

    const segmentLength = buffer.readUInt16BE(offset)

    if (segmentLength < 2 || offset + segmentLength > buffer.length) {
      break
    }

    const isStartOfFrame =
      (marker >= 0xc0 && marker <= 0xc3) ||
      (marker >= 0xc5 && marker <= 0xc7) ||
      (marker >= 0xc9 && marker <= 0xcb) ||
      (marker >= 0xcd && marker <= 0xcf)

    if (isStartOfFrame) {
      return {
        width: buffer.readUInt16BE(offset + 5),
        height: buffer.readUInt16BE(offset + 3)
      }
    }

    offset += segmentLength
  }

  return null
}

function readWebpMeta(buffer: Buffer) {
  if (
    buffer.length < 16 ||
    buffer.toString('ascii', 0, 4) !== 'RIFF' ||
    buffer.toString('ascii', 8, 12) !== 'WEBP'
  ) {
    return null
  }

  let offset = 12

  while (offset + 8 <= buffer.length) {
    const chunkType = buffer.toString('ascii', offset, offset + 4)
    const chunkSize = buffer.readUInt32LE(offset + 4)
    const chunkDataOffset = offset + 8

    if (chunkType === 'VP8X' && chunkDataOffset + 10 <= buffer.length) {
      return {
        width: readUInt24LE(buffer, chunkDataOffset + 4) + 1,
        height: readUInt24LE(buffer, chunkDataOffset + 7) + 1
      }
    }

    if (chunkType === 'VP8 ' && chunkDataOffset + 10 <= buffer.length) {
      return {
        width: buffer.readUInt16LE(chunkDataOffset + 6) & 0x3fff,
        height: buffer.readUInt16LE(chunkDataOffset + 8) & 0x3fff
      }
    }

    if (chunkType === 'VP8L' && chunkDataOffset + 5 <= buffer.length) {
      const b0 = buffer[chunkDataOffset + 1]
      const b1 = buffer[chunkDataOffset + 2]
      const b2 = buffer[chunkDataOffset + 3]
      const b3 = buffer[chunkDataOffset + 4]

      return {
        width: 1 + (((b1 & 0x3f) << 8) | b0),
        height: 1 + (((b3 & 0x0f) << 10) | (b2 << 2) | ((b1 & 0xc0) >> 6))
      }
    }

    offset = chunkDataOffset + chunkSize + (chunkSize % 2)
  }

  return null
}

function readUInt24LE(buffer: Buffer, offset: number) {
  return buffer[offset] | (buffer[offset + 1] << 8) | (buffer[offset + 2] << 16)
}

function escapeAttribute(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

function renderDocImage(token: any) {
  const src = token.attrGet('src') ?? ''

  if (!src) {
    return ''
  }

  const alt = token.content ?? ''
  const title = token.attrGet('title') ?? ''
  const meta = imageMetaMap[src]
  const attributes = [
    `src="${escapeAttribute(src)}"`,
    `alt="${escapeAttribute(alt)}"`
  ]

  if (title) {
    attributes.push(`title="${escapeAttribute(title)}"`)
  }

  if (meta?.width && meta?.height) {
    attributes.push(`width="${meta.width}"`)
    attributes.push(`height="${meta.height}"`)
  }

  return `<DocImage ${attributes.join(' ')}></DocImage>`
}

// https://vitepress.dev/reference/site-config
export default defineConfig({
  base: '/NeatReel/',
  title: "净影连 NeatReel",
  description: "去黑边，正朝向，一键拼出好影像",
  markdown: {
    config(md) {
      md.renderer.rules.image = (tokens, index) => renderDocImage(tokens[index])
    }
  },
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
