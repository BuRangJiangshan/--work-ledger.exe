import { reactive } from 'vue'
import api from './api'

export const store = reactive({
  meta: null,
  settings: {},
  recent: [],
  loaded: false,
})

export async function loadMeta() {
  const { data } = await api.get('/api/meta')
  store.meta = data
  store.settings = data.settings || {}
  store.loaded = true
  return data
}

export function statusLabel(value) {
  return store.meta?.statuses?.find((s) => s.value === value)?.label || value
}

export function statusColor(value) {
  return store.meta?.statuses?.find((s) => s.value === value)?.color || 'info'
}

export function actionLabel(value) {
  return store.meta?.action_types?.find((a) => a.value === value)?.label || value
}

export function relationLabel(value) {
  return store.meta?.relation_types?.find((r) => r.value === value)?.label || value
}
