<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { withBase } from 'vitepress'

defineOptions({
  name: 'DocImage'
})

type Variant = 'default' | 'avatar'

const loadedImageCache = new Set<string>()

const props = withDefaults(
  defineProps<{
    src: string
    alt?: string
    title?: string
    width?: number | string
    height?: number | string
    variant?: Variant
  }>(),
  {
    alt: '',
    title: '',
    width: undefined,
    height: undefined,
    variant: 'default'
  }
)

function resolveImageSrc(src: string) {
  if (/^(?:https?:|data:|blob:)/.test(src)) {
    return src
  }

  return withBase(src)
}

const initialResolvedSrc = resolveImageSrc(props.src)
const imageRef = ref<HTMLImageElement | null>(null)
const isLoaded = ref(loadedImageCache.has(initialResolvedSrc))
const isError = ref(false)

const numericWidth = computed(() => toPositiveNumber(props.width))
const numericHeight = computed(() => toPositiveNumber(props.height))
const hasDimensions = computed(() => Boolean(numericWidth.value && numericHeight.value))
const dimensionLabel = computed(() =>
  numericWidth.value && numericHeight.value
    ? `${numericWidth.value} x ${numericHeight.value}`
    : ''
)
const aspectRatio = computed(() =>
  numericWidth.value && numericHeight.value
    ? `${numericWidth.value} / ${numericHeight.value}`
    : undefined
)
const resolvedSrc = computed(() => resolveImageSrc(props.src))
const placeholderLabel = computed(() => (isError.value ? 'Image unavailable' : 'Loading'))
const showPlaceholder = computed(() => !isLoaded.value)
const containerStyle = computed(() => {
  if (props.variant === 'avatar') {
    return {
      aspectRatio: aspectRatio.value
    }
  }

  return hasDimensions.value ? undefined : { width: '100%', minHeight: '240px' }
})

function toPositiveNumber(value?: number | string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined
}

function handleLoad() {
  loadedImageCache.add(resolvedSrc.value)
  isLoaded.value = true
  isError.value = false
}

function handleError() {
  isError.value = true
  isLoaded.value = false
}

onMounted(() => {
  const image = imageRef.value

  if (loadedImageCache.has(resolvedSrc.value)) {
    isLoaded.value = true
    isError.value = false
    return
  }

  if (image?.complete && image.naturalWidth > 0) {
    loadedImageCache.add(resolvedSrc.value)
    isLoaded.value = true
  }
})
</script>

<template>
  <span
    class="doc-image"
    :class="[
      `doc-image--${variant}`,
      { 'doc-image--sized': hasDimensions, 'is-loaded': isLoaded, 'is-error': isError }
    ]"
    :style="containerStyle"
  >
    <span v-if="showPlaceholder" class="doc-image__placeholder" aria-hidden="true">
      <span class="doc-image__sheen"></span>
      <span class="doc-image__spinner"></span>
      <span v-if="dimensionLabel" class="doc-image__resolution">{{ dimensionLabel }}</span>
      <span class="doc-image__label">{{ placeholderLabel }}</span>
    </span>

    <img
      ref="imageRef"
      class="doc-image__img"
      :src="resolvedSrc"
      :alt="alt"
      :title="title || undefined"
      :width="numericWidth"
      :height="numericHeight"
      decoding="async"
      @load="handleLoad"
      @error="handleError"
    >
  </span>
</template>

<style scoped>
.doc-image {
  position: relative;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 18px;
  background:
    radial-gradient(circle at 22% 18%, rgba(56, 189, 248, 0.16), transparent 34%),
    linear-gradient(140deg, #05070d 0%, #0f172a 58%, #111827 100%);
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.18);
}

.doc-image--avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 999px;
  border-color: rgba(148, 163, 184, 0.14);
  background:
    radial-gradient(circle at 28% 24%, rgba(255, 255, 255, 0.18), transparent 32%),
    linear-gradient(140deg, #111827 0%, #1f2937 100%);
  box-shadow: none;
}

.doc-image__placeholder {
  position: absolute;
  inset: 0;
}

.doc-image__placeholder {
  display: grid;
  place-items: center;
  gap: 0.65rem;
  padding: 1.2rem;
  text-align: center;
}

.doc-image__sheen {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 24%, rgba(255, 255, 255, 0.12) 50%, transparent 76%);
  transform: translateX(-100%);
  animation: doc-image-sheen 1.9s ease-in-out infinite;
}

.doc-image__spinner {
  width: 46px;
  height: 46px;
  border: 3px solid rgba(255, 255, 255, 0.18);
  border-top-color: rgba(255, 255, 255, 0.92);
  border-radius: 999px;
  animation: doc-image-spin 0.9s linear infinite;
}

.doc-image--avatar .doc-image__spinner {
  width: 28px;
  height: 28px;
  border-width: 2px;
}

.doc-image__resolution {
  position: relative;
  z-index: 1;
  font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Consolas, monospace;
  font-size: 0.78rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.doc-image__label {
  position: relative;
  z-index: 1;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.72);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.doc-image__img {
  display: block;
  max-width: 100%;
  height: auto;
  opacity: 0;
  transform: scale(1.015);
  transition:
    opacity 0.35s ease,
    transform 0.55s ease;
}

.doc-image--avatar .doc-image__img {
  width: 100%;
  height: 100%;
  max-width: none;
}

.doc-image:not(.doc-image--sized):not(.doc-image--avatar) .doc-image__img {
  width: 100%;
}

.doc-image--avatar .doc-image__img {
  object-fit: cover;
}

.doc-image.is-loaded .doc-image__img {
  opacity: 1;
  transform: scale(1);
}

.doc-image.is-loaded .doc-image__placeholder {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.28s ease;
}

.doc-image.is-error .doc-image__spinner {
  animation: none;
  border-top-color: rgba(248, 113, 113, 0.92);
}

@keyframes doc-image-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes doc-image-sheen {
  to {
    transform: translateX(100%);
  }
}

@media (max-width: 640px) {
  .doc-image__resolution {
    font-size: 0.72rem;
  }

  .doc-image__label {
    font-size: 0.76rem;
  }
}
</style>
