<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import api from './api'
import { loadMeta, store } from './store'
import { todayStr } from './utils'

const route = useRoute()
const router = useRouter()
const recent = ref([])
const closeNotified = ref(sessionStorage.getItem('close-notified') === todayStr())

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/items/new') return '/items/new'
  if (/^\/items\/\d+/.test(path)) return '/items'
  return path
})

const menus = [
  { path: '/', icon: 'HomeFilled', label: '今日工作台' },
  { path: '/items/new', icon: 'EditPen', label: '事项登记' },
  { path: '/items', icon: 'Tickets', label: '事项台账' },
  { path: '/timeline', icon: 'Clock', label: '全局时间线' },
  { path: '/daily-close', icon: 'Sunset', label: '每日收尾' },
  { path: '/reports', icon: 'Document', label: '汇报中心' },
  { path: '/stats', icon: 'DataAnalysis', label: '统计视图' },
  { path: '/repeats', icon: 'Refresh', label: '重复任务' },
  { path: '/settings', icon: 'Setting', label: '设置' },
]

function quickAdd() {
  router.push('/items/new')
}

function onKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === 'n') {
    event.preventDefault()
    quickAdd()
  }
}

async function refreshRecent() {
  const { data } = await api.get('/api/dashboard')
  recent.value = (data.recent || []).slice(0, 5)
}

function openItem(command) {
  router.push(`/items/${command}`)
}

function pad(n) {
  return String(n).padStart(2, '0')
}

async function checkDailyClose() {
  if (closeNotified.value) return
  try {
    if (!store.loaded) await loadMeta()
    if (store.settings.close_enabled === false) return
    const { data } = await api.get('/api/daily-close', { params: { date: todayStr() } })
    if (data.log) return
    const remind = store.settings.close_remind_time || '17:30'
    const now = new Date()
    const current = `${pad(now.getHours())}:${pad(now.getMinutes())}`
    if (current < remind) return
    closeNotified.value = true
    sessionStorage.setItem('close-notified', todayStr())
    ElNotification({
      title: '每日收尾提醒',
      message: '今天还没有做收尾，花一分钟回顾今日工作。点击进入每日收尾页面。',
      type: 'warning',
      duration: 0,
      onClick: () => router.push('/daily-close'),
    })
  } catch (error) {
    /* 静默失败，不影响主流程 */
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  if (!store.loaded) loadMeta()
  setTimeout(checkDailyClose, 800)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="206px" class="app-aside">
      <div class="brand">
        <span class="logo">痕</span>
        <span>事项留痕工具</span>
      </div>
      <div class="menu-scroll">
        <el-menu class="side-menu" :default-active="activeMenu" router>
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>
      </div>
      <div class="aside-footer">事事留痕 · 全程可溯</div>
    </el-aside>

    <el-container>
      <el-header class="app-header" height="64px">
        <span class="header-title">{{ route.meta.title || '今日工作台' }}</span>
        <span class="header-spacer" />
        <el-button type="primary" @click="quickAdd">
          <el-icon><Plus /></el-icon>
          <span>快速登记</span>
          <span class="small" style="opacity: 0.7">Ctrl+N</span>
        </el-button>
        <el-dropdown trigger="click" @visible-change="(v) => v && refreshRecent()">
          <el-button plain>
            <el-icon><Clock /></el-icon>
            最近查看
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="!recent.length" disabled>暂无最近查看</el-dropdown-item>
              <el-dropdown-item
                v-for="item in recent"
                :key="item.id"
                :command="item.id"
                @click="openItem(item.id)"
              >
                {{ item.item_no }} · {{ item.title }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <span class="header-date">{{ todayStr() }}</span>
      </el-header>

      <el-main style="padding: 0">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
