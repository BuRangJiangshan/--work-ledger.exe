<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { store } from '../store'
import { fmtDT } from '../utils'

const loading = ref(false)
const rules = ref([])
const dialog = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  title: '',
  category: '日常事务',
  source_type: '其他',
  trigger_type: 'fixed',
  freq: 'weekly',
  weekday: 0,
  monthDay: 5,
  time: '09:00',
  after_done_days: 30,
  backlog_strategy: 'keep_all',
  enabled: true,
})

const categories = computed(() => store.meta?.categories || [])
const sourceTypes = computed(() => store.meta?.source_types || [])
const weekdays = [
  { value: 0, label: '周一' },
  { value: 1, label: '周二' },
  { value: 2, label: '周三' },
  { value: 3, label: '周四' },
  { value: 4, label: '周五' },
  { value: 5, label: '周六' },
  { value: 6, label: '周日' },
]

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/repeats')
    rules.value = data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    title: '',
    category: '日常事务',
    source_type: '其他',
    trigger_type: 'fixed',
    freq: 'weekly',
    weekday: 0,
    monthDay: 5,
    time: '09:00',
    after_done_days: 30,
    backlog_strategy: 'keep_all',
    enabled: true,
  })
  dialog.value = true
}

function openEdit(rule) {
  editingId.value = rule.id
  const schedule = rule.schedule || {}
  Object.assign(form, {
    name: rule.name,
    title: rule.item_template?.title || '',
    category: rule.item_template?.category || '日常事务',
    source_type: rule.item_template?.source_type || '其他',
    trigger_type: rule.trigger_type,
    freq: schedule.freq || 'weekly',
    weekday: schedule.weekday ?? 0,
    monthDay: schedule.day || 5,
    time: schedule.time || '09:00',
    after_done_days: rule.after_done_days || 30,
    backlog_strategy: rule.backlog_strategy || 'keep_all',
    enabled: rule.enabled,
  })
  dialog.value = true
}

function scheduleText(rule) {
  if (rule.trigger_type === 'after_done') {
    return `办结后 ${rule.after_done_days} 天`
  }
  const s = rule.schedule || {}
  const time = s.time || '09:00'
  if (s.freq === 'daily') return `每天 ${time}`
  if (s.freq === 'monthly') return `每月 ${s.day || 1} 日 ${time}`
  return `每${weekdays.find((w) => w.value === (s.weekday ?? 0))?.label.slice(1) || '周一'} ${time}`
}

async function submit() {
  if (!form.name.trim() || !form.title.trim()) {
    ElMessage.warning('请填写规则名称和事项标题')
    return
  }
  const payload = {
    name: form.name.trim(),
    item_template: {
      title: form.title.trim(),
      category: form.category,
      source_type: form.source_type,
    },
    trigger_type: form.trigger_type,
    backlog_strategy: form.backlog_strategy,
    enabled: form.enabled,
    after_done_days: form.trigger_type === 'after_done' ? Number(form.after_done_days) : null,
    schedule:
      form.trigger_type === 'fixed'
        ? form.freq === 'weekly'
          ? { freq: 'weekly', weekday: Number(form.weekday), time: form.time }
          : form.freq === 'monthly'
            ? { freq: 'monthly', day: Number(form.monthDay), time: form.time }
            : { freq: 'daily', time: form.time }
        : null,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await api.patch(`/api/repeats/${editingId.value}`, payload)
      ElMessage.success('规则已更新')
    } else {
      await api.post('/api/repeats', payload)
      ElMessage.success('规则已创建，系统将按时自动生成事项')
    }
    dialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(rule, value) {
  await api.patch(`/api/repeats/${rule.id}`, { enabled: value })
  rule.enabled = value
}

async function removeRule(rule) {
  try {
    await ElMessageBox.confirm(`确定删除规则「${rule.name}」？`, '提示', { type: 'warning' })
    await api.delete(`/api/repeats/${rule.id}`)
    ElMessage.success('已删除')
    load()
  } catch (error) {
    /* 取消 */
  }
}

async function processNow() {
  const { data } = await api.post('/api/repeats/process')
  ElMessage.success(data.count ? `已生成 ${data.count} 条事项` : '当前没有到期需要生成的事项')
  load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">重复任务</h2>
        <div class="page-subtitle">
          周期性工作自动生成事项；默认“保留全部”，漏办也留痕可追溯
        </div>
      </div>
      <div>
        <el-button plain @click="processNow">立即生成到期事项</el-button>
        <el-button type="primary" @click="openCreate">新建规则</el-button>
      </div>
    </div>

    <div class="card" style="padding: 10px 12px 14px">
      <el-table :data="rules" stripe>
        <el-table-column prop="name" label="规则名称" min-width="200" />
        <el-table-column label="触发生成事项" min-width="200">
          <template #default="{ row }">
            {{ row.item_template?.title }}
          </template>
        </el-table-column>
        <el-table-column label="触发方式" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="row.trigger_type === 'fixed' ? 'primary' : 'success'">
              {{ row.trigger_type === 'fixed' ? '固定周期' : '办结后触发' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="周期" width="150">
          <template #default="{ row }">{{ scheduleText(row) }}</template>
        </el-table-column>
        <el-table-column label="堆积策略" width="120">
          <template #default="{ row }">
            {{ row.backlog_strategy === 'latest_only' ? '只留最新' : '保留全部' }}
          </template>
        </el-table-column>
        <el-table-column label="下次生成" width="150">
          <template #default="{ row }">{{ fmtDT(row.next_run_time) || '—' }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="(v) => toggleEnabled(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!rules.length" description="暂无重复任务规则" />
    </div>

    <el-dialog v-model="dialog" :title="editingId ? '编辑重复任务规则' : '新建重复任务规则'" width="600px">
      <el-form label-width="110px">
        <el-form-item label="规则名称" required>
          <el-input v-model="form.name" placeholder="如：每周一上传周报台账" />
        </el-form-item>
        <el-form-item label="生成事项标题" required>
          <el-input v-model="form.title" placeholder="可用 {date} 占位，如：办结后回访 {date}" />
        </el-form-item>
        <div class="grid-2">
          <el-form-item label="事项类别">
            <el-select v-model="form.category" style="width: 100%">
              <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源类型">
            <el-select v-model="form.source_type" style="width: 100%">
              <el-option v-for="s in sourceTypes" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="触发方式">
          <el-radio-group v-model="form.trigger_type">
            <el-radio value="fixed">固定周期</el-radio>
            <el-radio value="after_done">完成后 N 天再触发</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.trigger_type === 'fixed'">
          <el-form-item label="周期类型">
            <el-radio-group v-model="form.freq">
              <el-radio value="daily">每天</el-radio>
              <el-radio value="weekly">每周</el-radio>
              <el-radio value="monthly">每月</el-radio>
            </el-radio-group>
          </el-form-item>
          <div class="grid-2">
            <el-form-item v-if="form.freq === 'weekly'" label="星期">
              <el-select v-model="form.weekday" style="width: 100%">
                <el-option v-for="w in weekdays" :key="w.value" :label="w.label" :value="w.value" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="form.freq === 'monthly'" label="每月几日">
              <el-input-number v-model="form.monthDay" :min="1" :max="28" style="width: 100%" />
            </el-form-item>
            <el-form-item label="生成时间">
              <el-input v-model="form.time" placeholder="09:00" />
            </el-form-item>
          </div>
        </template>
        <el-form-item v-else label="间隔天数">
          <el-input-number v-model="form.after_done_days" :min="1" style="width: 200px" />
          <span class="form-tip" style="margin-left: 8px">上次办结后第 N 天生成下一次事项</span>
        </el-form-item>
        <el-form-item label="堆积策略">
          <el-radio-group v-model="form.backlog_strategy">
            <el-radio value="keep_all">保留全部（默认，漏办也留痕）</el-radio>
            <el-radio value="latest_only">只留最新</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存规则</el-button>
      </template>
    </el-dialog>
  </div>
</template>
