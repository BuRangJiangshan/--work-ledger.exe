<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import StatusTag from '../components/StatusTag.vue'
import { reminderTag, todayStr } from '../utils'

const router = useRouter()
const data = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const resp = await api.get('/api/dashboard')
    data.value = resp.data
  } finally {
    loading.value = false
  }
}

function openItem(id) {
  router.push(`/items/${id}`)
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">今日工作台</h2>
        <div class="page-subtitle">{{ data?.date || todayStr() }} · 事事留痕，全程可溯</div>
      </div>
      <div>
        <el-button plain @click="load">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" @click="router.push('/items/new')">
          <el-icon><Plus /></el-icon>登记新事项
        </el-button>
      </div>
    </div>

    <div class="stat-grid" v-if="data">
      <div class="stat-card green">
        <div class="stat-label">今日办结</div>
        <div class="stat-value">{{ data.counts.finished_today }}<span class="unit">件</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日汇报</div>
        <div class="stat-value">{{ data.counts.reports_today }}<span class="unit">次</span></div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-label">今日催办</div>
        <div class="stat-value">{{ data.counts.urges_today }}<span class="unit">次</span></div>
      </div>
      <div class="stat-card red">
        <div class="stat-label">超期未办</div>
        <div class="stat-value">{{ data.counts.overdue }}<span class="unit">件</span></div>
      </div>
    </div>

    <div class="card" v-if="data?.pinned?.length">
      <div class="card-title">
        <el-icon color="#e6a23c"><StarFilled /></el-icon>
        置顶事项
        <span class="count">{{ data.pinned.length }} 件</span>
      </div>
      <div v-for="item in data.pinned" :key="item.id" class="item-row">
        <span class="no">{{ item.item_no }}</span>
        <span class="title" @click="openItem(item.id)">{{ item.title }}</span>
        <StatusTag :status="item.status" />
        <el-tag size="small" :type="reminderTag(item).type" effect="plain">
          {{ reminderTag(item).text }}
        </el-tag>
      </div>
    </div>

    <div class="card" v-if="data">
      <div class="card-title">
        临期看板
        <span class="count">红黄绿三档 · 共 {{ data.counts.open_total }} 件未办结</span>
      </div>
      <el-row :gutter="14">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="bucket red">
            <div class="bucket-head">
              <span>🔴 今日到期 / 超期</span><span>{{ data.red.length }}</span>
            </div>
            <div v-for="item in data.red.slice(0, 8)" :key="item.id" class="item-row">
              <span class="title small" @click="openItem(item.id)">{{ item.title }}</span>
              <el-tag size="small" type="danger" effect="plain">
                {{ item.remaining_days < 0 ? `超期${Math.abs(item.remaining_days)}天` : '今日到期' }}
              </el-tag>
            </div>
            <div v-if="!data.red.length" class="muted small">暂无</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="bucket yellow">
            <div class="bucket-head">
              <span>🟡 3 天内到期</span><span>{{ data.yellow.length }}</span>
            </div>
            <div v-for="item in data.yellow.slice(0, 8)" :key="item.id" class="item-row">
              <span class="title small" @click="openItem(item.id)">{{ item.title }}</span>
              <span class="small muted">剩 {{ item.remaining_days }} 天</span>
            </div>
            <div v-if="!data.yellow.length" class="muted small">暂无</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="bucket green">
            <div class="bucket-head">
              <span>🟢 时限充裕</span><span>{{ data.green.length }}</span>
            </div>
            <div v-for="item in data.green.slice(0, 8)" :key="item.id" class="item-row">
              <span class="title small" @click="openItem(item.id)">{{ item.title }}</span>
              <span class="small muted">剩 {{ item.remaining_days }} 天</span>
            </div>
            <div v-if="!data.green.length" class="muted small">暂无</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="bucket none">
            <div class="bucket-head">
              <span>⚪ 无明确时限</span><span>{{ data.no_due.length }}</span>
            </div>
            <div v-for="item in data.no_due.slice(0, 8)" :key="item.id" class="item-row">
              <span class="title small" @click="openItem(item.id)">{{ item.title }}</span>
              <StatusTag :status="item.status" />
            </div>
            <div v-if="!data.no_due.length" class="muted small">暂无</div>
          </div>
        </el-col>
      </el-row>
    </div>

    <el-row :gutter="16" v-if="data">
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">今日新增 <span class="count">{{ data.created_today.length }} 件</span></div>
          <div v-for="item in data.created_today" :key="item.id" class="item-row">
            <span class="no">{{ item.item_no }}</span>
            <span class="title" @click="openItem(item.id)">{{ item.title }}</span>
          </div>
          <div v-if="!data.created_today.length" class="muted small">今天还没有新增记录</div>
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">今日待汇报 <span class="count">{{ data.todo_report.length }} 件</span></div>
          <div v-for="item in data.todo_report" :key="item.id" class="item-row">
            <span class="no">{{ item.item_no }}</span>
            <span class="title" @click="openItem(item.id)">{{ item.title }}</span>
            <StatusTag :status="item.status" />
          </div>
          <div v-if="!data.todo_report.length" class="muted small">暂无待汇报事项</div>
        </div>
      </el-col>
      <el-col :xs="24" :md="8">
        <div class="card">
          <div class="card-title">待催办 <span class="count">{{ data.todo_urge.length }} 件</span></div>
          <div v-for="item in data.todo_urge" :key="item.id" class="item-row">
            <span class="no">{{ item.item_no }}</span>
            <span class="title" @click="openItem(item.id)">{{ item.title }}</span>
            <el-tag size="small" :type="reminderTag(item).type" effect="plain">
              {{ reminderTag(item).text }}
            </el-tag>
          </div>
          <div v-if="!data.todo_urge.length" class="muted small">暂无临期待催办事项</div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>
