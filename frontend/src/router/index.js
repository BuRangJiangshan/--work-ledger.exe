import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '今日工作台' } },
  { path: '/items/new', name: 'item-new', component: () => import('../views/ItemForm.vue'), meta: { title: '事项登记' } },
  { path: '/items', name: 'ledger', component: () => import('../views/Ledger.vue'), meta: { title: '事项台账' } },
  { path: '/items/:id', name: 'item-detail', component: () => import('../views/ItemDetail.vue'), meta: { title: '事项详情' } },
  { path: '/timeline', name: 'timeline', component: () => import('../views/Timeline.vue'), meta: { title: '全局时间线' } },
  { path: '/daily-close', name: 'daily-close', component: () => import('../views/DailyClose.vue'), meta: { title: '每日收尾' } },
  { path: '/reports', name: 'reports', component: () => import('../views/Reports.vue'), meta: { title: '汇报中心' } },
  { path: '/stats', name: 'stats', component: () => import('../views/Stats.vue'), meta: { title: '统计视图' } },
  { path: '/repeats', name: 'repeats', component: () => import('../views/Repeats.vue'), meta: { title: '重复任务' } },
  { path: '/settings', name: 'settings', component: () => import('../views/Settings.vue'), meta: { title: '设置' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 事项办理全程留痕工具` : '事项办理全程留痕工具'
})

export default router
