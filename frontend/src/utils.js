export function fmtDate(value) {
  return value ? String(value).slice(0, 10) : ''
}

export function fmtDT(value) {
  return value ? String(value).replace('T', ' ') : ''
}

export function todayStr() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function nowInput() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function monthRange() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const start = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`
  return [start, todayStr()]
}

export function reminderTag(item) {
  if (item.status === 'finished') return { type: 'success', text: '已办结' }
  if (!item.due_date) return { type: 'info', text: '无时限' }
  if (item.remaining_days < 0) return { type: 'danger', text: `超期 ${Math.abs(item.remaining_days)} 天` }
  if (item.remaining_days === 0) return { type: 'danger', text: '今日到期' }
  return { type: item.remaining_days <= 3 ? 'warning' : 'success', text: `剩余 ${item.remaining_days} 天` }
}

export function actionColor(action) {
  return (
    {
      report: '#409eff',
      instruction: '#e6a23c',
      finish: '#67c23a',
      delay: '#f56c6c',
      reopen: '#9b59b6',
      assign: '#1d5bd6',
      urge: '#b88230',
      progress: '#606266',
      feedback: '#909399',
    }[action] || '#909399'
  )
}

export function downloadByUrl(url) {
  const link = document.createElement('a')
  link.href = url
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
