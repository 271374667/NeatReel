import DefaultTheme from 'vitepress/theme'
import DocImage from './DocImage.vue'
import './custom.css'

export default {
  ...DefaultTheme,
  enhanceApp({ app }) {
    DefaultTheme.enhanceApp?.({ app })
    app.component('DocImage', DocImage)
  }
}
