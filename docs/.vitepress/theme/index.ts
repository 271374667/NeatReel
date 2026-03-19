import DefaultTheme from 'vitepress/theme'
import DocImage from './DocImage.vue'
import './custom.css'

const localeStorageKey = 'neatreel-docs-locale-initialized'
const siteBase = '/NeatReel/'

function redirectOnFirstVisit() {
  if (typeof window === 'undefined') {
    return
  }

  const currentPath = window.location.pathname
  const isEntry =
    currentPath === siteBase ||
    currentPath === `${siteBase}index.html`

  if (!isEntry) {
    return
  }

  if (window.localStorage.getItem(localeStorageKey) === '1') {
    return
  }

  const preferredLanguage = (navigator.language || '').toLowerCase()
  const targetPath = preferredLanguage.startsWith('zh') ? `${siteBase}zh/` : siteBase
  window.localStorage.setItem(localeStorageKey, '1')

  if (targetPath !== currentPath) {
    window.location.replace(targetPath)
  }
}

export default {
  ...DefaultTheme,
  enhanceApp({ app }) {
    DefaultTheme.enhanceApp?.({ app })
    app.component('DocImage', DocImage)
    redirectOnFirstVisit()
  }
}
