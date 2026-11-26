<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { downloadByUrl } from '../utils'
import { loadMeta, store } from '../store'

const loading = ref(false)
const saving = ref(false)
const settings = reactive({
  close_enabled: true,
  close_remind_time: '17:30',
  unit_name: '',
  estimate_defaults: {},
  urge_days: '3,1,0',
})

const categories = ref([])

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/settings')
    settings.close_enabled = data.close_enabled !== false
    settings.close_remind_time = data.close_remind_time || '17:30'
    settings.unit_name = data.unit_name || ''
    settings.estimate_defaults = { ...(data.estimate_defaults || {}) }
    settings.urge_days = (data.urge_rules?.remaining_days || [3, 1, 0]).join(',')
    categories.value = Object.keys(settings.estimate_defaults)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const remaining = settings.urge_days
      .split(',')
      .map((v) => Number(v.trim()))
      .filter((v) => !Number.isNaN(v))
    const { data } = await api.put('/api/settings', {
      close_enabled: settings.close_enabled,
      close_remind_time: settings.close_remind_time,
      unit_name: settings.unit_name,
      estimate_defaults: settings.estimate_defaults,
      urge_rules: {
        remaining_days: remaining.length ? remaining : [3, 1, 0],
        overdue_daily: true,
      },
    })
    store.settings = data
    ElMessage.success('设置已保存')
  } finally {
    saving.value = false
  }
}

async function backup() {
  try {
    const { data } = await api.post('/api/backup')
    ElMessageBox.alert(data.file, '备份完成（SQLite 在线备份接口）', {
      type: 'success',
      confirmButtonText: '知道了',
    })
  } catch (error) {
    /* 已提示 */
  }
}

onMounted(() => {
  load().then(loadMeta)
})
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">设置</h2>
        <div class="page-subtitle">数据全部保存在本机，不上传公网、无遥测</div>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
    </div>

    <div class="card">
      <div class="card-title">每日收尾</div>
      <el-form label-width="140px">
        <el-form-item label="启用收尾提醒">
          <el-switch v-model="settings.close_enabled" />
        </el-form-item>
        <el-form-item label="固定提醒时间">
          <el-time-picker
            v-model="settings.close_remind_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="17:30"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="单位名称">
          <el-input
            v-model="settings.unit_name"
            placeholder="用于汇报标题，如：XX街道"
            style="width: 320px"
          />
        </el-form-item>
        <el-form-item label="临期提醒节点">
          <el-input v-model="settings.urge_days" style="width: 200px" placeholder="3,1,0" />
          <span class="form-tip" style="margin-left: 8px">剩余天数，逗号分隔（0 表示当日到期）</span>
        </el-form-item>
      </el-form>
    </div>

    <div class="card">
      <div class="card-title">各类别默认办理时长（自然日）</div>
      <el-form label-width="140px">
        <el-form-item v-for="c in categories" :key="c" :label="c">
          <el-input-number v-model="settings.estimate_defaults[c]" :min="0" :controls="false" style="width: 160px" />
          <span class="form-tip" style="margin-left: 8px">个自然日</span>
        </el-form-item>
        <div class="form-tip">
          单位换算仅用于界面展示：综治工单 9 自然日 ≈ 7 个工作日；存储、统计与偏差分析一律使用自然日。
        </div>
      </el-form>
    </div>

    <div class="card">
      <div class="card-title">数据备份与导出</div>
      <div style="display: flex; gap: 12px; flex-wrap: wrap">
        <el-button @click="backup">
          <el-icon><FolderOpened /></el-icon>立即备份（在线备份接口）
        </el-button>
        <el-button plain @click="downloadByUrl('/api/export/xlsx')">导出 Excel</el-button>
        <el-button plain @click="downloadByUrl('/api/export/csv')">导出 CSV</el-button>
        <el-button plain @click="downloadByUrl('/api/export/json')">导出 JSON 全量数据</el-button>
      </div>
      <div class="form-tip" style="margin-top: 10px">
        备份使用 SQLite 官方在线备份接口，避免写入过程中复制文件产生不一致快照；备份文件保存在数据目录 backups 下。
        全量 JSON 导出包含事项、过程记录、关系、审计历史等全部表，可随时迁移。
      </div>
    </div>

    <div class="card">
      <div class="card-title">关于</div>
      <div class="small" style="line-height: 2">
        <div>应用形态：本地网页应用（FastAPI + SQLite + Vue 3 / Element Plus），浏览器访问 localhost。</div>
        <div>数据位置：数据目录下的 app.db；附件目录 attachments；备份目录 backups。</div>
        <div>审计历史：追加写入，数据库触发器强制禁止修改与删除。</div>
        <div>当前版本：V1.0（M1–M4 全部功能）</div>
      </div>
    </div>
  </div>
</template>
