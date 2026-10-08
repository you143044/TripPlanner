import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('./views/Home.vue')
    },
    {
      path: '/result',
      name: 'Result',
      component: () => import('./views/Result.vue')
    },
    {
      path: '/history',
      name: 'History',
      component: () => import('./views/History.vue')
    }
  ]
})

const app = createApp(App)

app.use(router)
app.use(Antd)

app.mount('#app')

