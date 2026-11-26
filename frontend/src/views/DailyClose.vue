<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { fmtDT, todayStr } from '../utils'
import { store } from '../store'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const day = ref(todayStr())
const summary = ref(null)
const skipDialog = ref(false)
const skipReason = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/daily-close', { params: { date: day.value } })
    summary.value = data
  } finally {
    loading.value = false
  }
}

async function confirmDone() {
  submitting.value = true
  try {
    await api.post('/api/daily-close', { date: day.value, status: 'done' })
    ElMessage.success('今日收尾已归档，已生成日报素材')
    load()
  } finally {
    submitting.value = false
  }
}

async function submitSkip() {
  submitting.value = true
  try {
    await api.post('/api/daily-close', {
      date: day.value,
      status: 'skipped',
      skip_reason: skipReason.value || null,
    })
    skipDialog.value = false
    skipReason.value = ''
    ElMessage.success('已记录跳过原因（跳过也留痕）')
    load()
  } finally {
    submitting.value = false
  }
}

function goReport() {
  router.push({ path: '/reports', query: { start: day.value, end: day.value } })
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">每日收尾</h2>
        <div class="page-subtitle">
          固定提醒时间 {{ store.settings?.close_remind_time || '17:30' }}（可在设置中调整）· 做了收尾要留痕，跳过也留痕
        </div>
      </div>
      <div style="display: flex; gap: 10px">
        <el-date-picker
          v-model="day"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 150px"
          @change="load"
        />
        <el-button plain @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="summary?.log"
      :type="summary.log.status === 'done' ? 'success' : 'info'"
      :title="summary.log.status === 'done' ? '今日收尾已完成并归档' : '今日收尾已跳过'"
      :description="
        summary.log.status === 'skipped'
          ? `跳过原因：${summary.log.skip_reason || '未填写'}（已留痕）`
          : '小结快照已沉淀，可直接用于日报素材。'
      "
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <div class="stat-grid" v-if="summary">
      <div class="stat-card green">
        <div class="stat-label">今日办结</div>
        <div class="stat-value">{{ summary.counts.finished }}<span class="unit">件</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日汇报 / 批示</div>
        <div class="stat-value">
          {{ summary.counts.reports }}<span class="unit">次</span>
          <span class="muted" style="font-size: 13px"> / {{ summary.counts.instructions }} 次</span>
        </div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-label">今日催办</div>
        <div class="stat-value">{{ summary.counts.urges }}<span class="unit">次</span></div>
      </div>
      <div class="stat-card red">
        <div class="stat-label">超期未办</div>
        <div class="stat-value">{{ summary.counts.overdue }}<span class="unit">件</span></div>
      </div>
    </div>

    <div class="card" v-if="summary">
      <div class="card-title">预估 vs 实际</div>
      <div v-if="summary.deviation.count">
        共 {{ summary.deviation.count }} 件有预估与实际对比，平均偏差
        <strong>{{ summary.deviation.avg > 0 ? '+' : '' }}{{ summary.deviation.avg }} 天</strong>，
        其中 {{ summary.deviation.over_estimate }} 件超出预估。
      </div>
      <div v-else class="muted small">今日办结事项暂无预估/实际可对比数据。</div>
    </div>

    <el-row :gutter="16" v-if="summary">
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">今日办结 <span class="count">{{ summary.finished.length }} 件</span></div>
          <div v-for="item in summary.finished" :key="item.id" class="item-row">
            <span class="title" @click="router.push(`/items/${item.id}`)">{{ item.title }}</span>
            <el-tag size="small" type="success" effect="plain">
              {{ item.actual_days }} 天
            </el-tag>
          </div>
          <div v-if="!summary.finished.length" class="muted small">今日暂无办结事项</div>
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">今日新增 <span class="count">{{ summary.created.length }} 件</span></div>
          <div v-for="item in summary.created" :key="item.id" class="item-row">
            <span class="no">{{ item.item_no }}</span>
            <span class="title" @click="router.push(`/items/${item.id}`)">{{ item.title }}</span>
          </div>
          <div v-if="!summary.created.length" class="muted small">今日暂无新增事项</div>
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">超期未办 <span class="count">{{ summary.overdue.length }} 件</span></div>
          <div v-for="item in summary.overdue" :key="item.id" class="item-row">
            <span class="title" @click="router.push(`/items/${item.id}`)">{{ item.title }}</span>
            <span class="small muted">应于 {{ item.due_date }} 办结</span>
          </div>
          <div v-if="!summary.overdue.length" class="muted small">暂无超期事项</div>
        </div>
      </el-col>
    </el-row>

    <div class="card" v-if="summary">
      <div class="card-title">收尾操作</div>
      <div v-if="!summary.log" style="display: flex; gap: 12px; flex-wrap: wrap">
        <el-button type="primary" size="large" :loading="submitting" @click="confirmDone">
          确认归档并生成日报素材
        </el-button>
        <el-button size="large" :loading="submitting" @click="skipDialog = true">
          跳过（原因选填）
        </el-button>
        <el-button size="large" plain @click="goReport">用当日素材生成日报</el-button>
      </div>
      <div v-else style="display: flex; gap: 12px; flex-wrap: wrap">
        <el-button type="primary" plain @click="goReport">用当日素材生成日报</el-button>
        <span class="muted" style="line-height: 34px">
          收尾记录时间：{{ fmtDT(summary.log.created_at) }}
        </span>
      </div>
    </div>

    <el-dialog v-model="skipDialog" title="跳过今日收尾" width="460px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="跳过也会记入收尾日志，保持台账完整可追溯。"
        style="margin-bottom: 12px"
      />
      <el-input
        v-model="skipReason"
        type="textarea"
        :rows="3"
        placeholder="跳过原因（选填），如：加班赶材料 / 外出开会 / 今日无事可记"
      />
      <template #footer>
        <el-button @click="skipDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitSkip">确认跳过</el-button>
      </template>
    </el-dialog>
  </div>
</template>
