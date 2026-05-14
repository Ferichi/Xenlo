import './assets/base.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import 'primeicons/primeicons.css'

import AppTheme from './themes/app-theme'

const app = createApp(App)

app.use(router)

app.use(PrimeVue, {
  theme: {
    preset: AppTheme,
    options: {
      darkModeSelector: false,
    },
  },
})

app.use(ToastService)

app.mount('#app')
