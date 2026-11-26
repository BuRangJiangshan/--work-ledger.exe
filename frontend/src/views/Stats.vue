<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { monthRange } from '../utils'

const range = ref(monthRange())
const stats = ref(null)
const loading = ref(false)
const monthlyRef = ref()
const sourceRef = ref()
const categoryRef = ref()
let charts = []

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/stats', {
      params: { start: range.value?.[0] || undefined, end: range.value?.[1] || undefined },
    })
    stats.value = data
    await nextTick()
    renderCharts()
  } finally {
    loading.value = false
  }
}

function resetCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
}

function renderCharts() {
  if (!stats.value) return
  resetCharts()

  if (monthlyRef.value) {
    const chart = echarts.init(monthlyRef.value)
    const months = stats.value.monthly.map((m) => m.month)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['接收', '办结'] },
      grid: { left: 40, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: months },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          name: '接收',
          type: 'bar',
          data: stats.value.monthly.map((m) => m.received),
          itemStyle: { color: '#1d5bd6', borderRadius: [4, 4, 0, 0] },
        },
        {
          name: '办结',
          type: 'bar',
          data: stats.value.monthly.map((m) => m.finished),
          itemStyle: { color: '#67c23a', borderRadius: [4, 4, 0, 0] },
        },
      ],
    })
    charts.push(chart)
  }

  if (sourceRef.value) {
    const chart = echarts.init(sourceRef.value)
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 件 ({d}%)' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          name: '来源分布',
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '44%'],
          data: stats.value.by_source.map((s) => ({ name: s.name, value: s.count })),
          label: { formatter: '{b}\n{c} 件' },
        },
      ],
    })
    charts.push(chart)
  }

  if (categoryRef.value) {
    const chart = echarts.init(categoryRef.value)
    const data = stats.value.by_category
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 90, right: 30, top: 20, bottom: 20 },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: { type: 'category', data: data.map((c) => c.name).reverse() },
      series: [
        {
          type: 'bar',
          data: data.map((c) => c.count).reverse(),
          itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right' },
        },
      ],
    })
    charts.push(chart)
  }
}

function onResize() {
  charts.forEach((c) => c.resize())
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  resetCharts()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">统计视图</h2>
        <div class="page-subtitle">
          自然日口径 · 按期 / 批准延期 / 超期三档分列 · 合并事项按主事项计一次
        </div>
      </div>
      <div style="display: flex; gap: 10px">
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          style="width: 260px"
          @change="load"
        />
        <el-button plain @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <template v-if="stats">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">接收事项</div>
          <div class="stat-value">{{ stats.total_received }}<span class="unit">件</span></div>
        </div>
        <div class="stat-card green">
          <div class="stat-label">已办结</div>
          <div class="stat-value">{{ stats.total_finished }}<span class="unit">件</span></div>
        </div>
        <div class="stat-card yellow">
          <div class="stat-label">按期办结率</div>
          <div class="stat-value">
            {{ stats.finish_rate === null ? '—' : stats.finish_rate }}
            <span class="unit" v-if="stats.finish_rate !== null">%</span>
          </div>
        </div>
        <div class="stat-card red">
          <div class="stat-label">预估 / 实际偏差</div>
          <div class="stat-value">
            {{ stats.deviation_avg === null ? '—' : stats.deviation_avg > 0 ? '+' + stats.deviation_avg : stats.deviation_avg }}
            <span class="unit" v-if="stats.deviation_avg !== null">天</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">办结口径分列</div>
        <el-row :gutter="16">
          <el-col :xs="12" :md="6">
            <div class="stat-label">按期办结</div>
            <div class="stat-value" style="color: #67c23a">{{ stats.on_time }}</div>
          </el-col>
          <el-col :xs="12" :md="6">
            <div class="stat-label">批准延期后办结</div>
            <div class="stat-value" style="color: #e6a23c">{{ stats.approved_delay }}</div>
          </el-col>
          <el-col :xs="12" :md="6">
            <div class="stat-label">超期办结</div>
            <div class="stat-value" style="color: #f56c6c">{{ stats.overdue }}</div>
          </el-col>
          <el-col :xs="12" :md="6">
            <div class="stat-label">无明确时限办结</div>
            <div class="stat-value" style="color: #909399">{{ stats.no_due }}</div>
          </el-col>
        </el-row>
        <div class="form-tip" style="margin-top: 10px">
          按期办结率 = 按期办结 ÷（按期 + 批准延期 + 超期），无明确时限事项不进入分母；
          延期件数 {{ stats.delayed_count }}，领导批示件 {{ stats.leader_instruction_count }} 件；
          平均实际用时 {{ stats.avg_actual_days ?? '—' }} 天，平均预估 {{ stats.avg_estimated_days ?? '—' }} 天，
          偏差分析样本 {{ stats.deviation_count }} 件（{{ stats.over_estimate_count }} 件超预估）。
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <div class="card">
            <div class="card-title">月度办件量</div>
            <div ref="monthlyRef" class="chart-box"></div>
          </div>
        </el-col>
        <el-col :xs="24" :lg="12">
          <div class="card">
            <div class="card-title">来源分布</div>
            <div ref="sourceRef" class="chart-box"></div>
          </div>
        </el-col>
        <el-col :xs="24" :lg="12">
          <div class="card">
            <div class="card-title">类别分布</div>
            <div ref="categoryRef" class="chart-box"></div>
          </div>
        </el-col>
        <el-col :xs="24" :lg="12">
          <div class="card">
            <div class="card-title">超期未办事项 <span class="count">{{ stats.overdue_items.length }} 件</span></div>
            <div v-for="item in stats.overdue_items" :key="item.id" class="item-row">
              <span class="no">{{ item.item_no }}</span>
              <router-link class="title" :to="`/items/${item.id}`" style="color: inherit">
                {{ item.title }}
              </router-link>
              <el-tag size="small" type="danger" effect="plain">
                超期 {{ Math.abs(item.remaining_days) }} 天
              </el-tag>
            </div>
            <div v-if="!stats.overdue_items.length" class="muted small">暂无超期事项</div>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>
