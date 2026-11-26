<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import StatusTag from '../components/StatusTag.vue'
import ItemPicker from '../components/ItemPicker.vue'
import { downloadByUrl, reminderTag } from '../utils'
import { store } from '../store'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const q = ref('')
const category = ref('')
const sourceType = ref('')
const statuses = ref([])
const receiveRange = ref([])
const dueRange = ref([])
const overdue = ref(false)
const instruction = ref(false)
const includeMerged = ref(false)
const sort = ref('recent')

const savedFilters = ref([])
const selectedFilter = ref(null)

const mergeDialog = ref(false)
const mergeSource = ref(null)
const mergeMaster = ref(null)
const mergeNote = ref('')
const merging = ref(false)

const categories = computed(() => store.meta?.categories || [])
const sourceTypes = computed(() => store.meta?.source_types || [])
const statusOptions = computed(() => store.meta?.statuses || [])

function buildParams() {
  return {
    q: q.value || undefined,
    category: category.value || undefined,
    source_type: sourceType.value || undefined,
    status: statuses.value.length ? statuses.value.join(',') : undefined,
    receive_from: receiveRange.value?.[0] || undefined,
    receive_to: receiveRange.value?.[1] || undefined,
    due_from: dueRange.value?.[0] || undefined,
    due_to: dueRange.value?.[1] || undefined,
    overdue: overdue.value || undefined,
    instruction: instruction.value || undefined,
    include_merged: includeMerged.value || undefined,
    sort: sort.value,
    page: page.value,
    page_size: pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/items', { params: buildParams() })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  q.value = ''
  category.value = ''
  sourceType.value = ''
  statuses.value = []
  receiveRange.value = []
  dueRange.value = []
  overdue.value = false
  instruction.value = false
  includeMerged.value = false
  sort.value = 'recent'
  selectedFilter.value = null
  search()
}

async function loadSaved() {
  const { data } = await api.get('/api/filters')
  savedFilters.value = data
}

function applySaved(id) {
  const target = savedFilters.value.find((f) => f.id === id)
  if (!target) return
  const f = target.filter_json || {}
  q.value = f.q || ''
  category.value = f.category || ''
  sourceType.value = f.source_type || ''
  statuses.value = f.status || []
  receiveRange.value = f.receive_range || []
  dueRange.value = f.due_range || []
  overdue.value = !!f.overdue
  instruction.value = !!f.instruction
  includeMerged.value = !!f.include_merged
  sort.value = f.sort || 'recent'
  page.value = 1
  load()
}

async function saveCurrent() {
  try {
    const { value } = await ElMessageBox.prompt('请输入过滤器名称', '保存当前筛选', {
      inputPlaceholder: '如：本周信访件、领导批示未办结',
      inputValidator: (v) => (v && v.trim() ? true : '名称不能为空'),
    })
    await api.post('/api/filters', {
      name: value.trim(),
      filter_json: {
        q: q.value,
        category: category.value,
        source_type: sourceType.value,
        status: statuses.value,
        receive_range: receiveRange.value || [],
        due_range: dueRange.value || [],
        overdue: overdue.value,
        instruction: instruction.value,
        include_merged: includeMerged.value,
        sort: sort.value,
      },
    })
    ElMessage.success('筛选方案已保存')
    loadSaved()
  } catch (error) {
    /* 取消 */
  }
}

async function removeSaved() {
  if (!selectedFilter.value) {
    ElMessage.warning('请先选择要删除的筛选方案')
    return
  }
  try {
    await ElMessageBox.confirm('确定删除该筛选方案？', '提示', { type: 'warning' })
    await api.delete(`/api/filters/${selectedFilter.value}`)
    selectedFilter.value = null
    loadSaved()
    ElMessage.success('已删除')
  } catch (error) {
    /* 取消 */
  }
}

function togglePin(row) {
  api.post(`/api/items/${row.id}/pin`, { pinned: !row.pinned }).then(() => load())
}

function openMerge(row) {
  mergeSource.value = row
  mergeMaster.value = null
  mergeNote.value = ''
  mergeDialog.value = true
}

async function submitMerge() {
  if (!mergeMaster.value) {
    ElMessage.warning('请选择主事项')
    return
  }
  merging.value = true
  try {
    const { data } = await api.post(`/api/items/${mergeSource.value.id}/merge`, {
      master_id: mergeMaster.value,
      note: mergeNote.value,
    })
    ElMessage.success(`已合并到主事项 ${data.item_no}，原记录全部保留`)
    mergeDialog.value = false
    load()
  } finally {
    merging.value = false
  }
}

function exportFile(kind) {
  downloadByUrl(`/api/export/${kind}`)
}

onMounted(() => {
  load()
  loadSaved()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">事项台账</h2>
        <div class="page-subtitle">共 {{ total }} 条记录（已合并事项默认隐藏，统计按主事项计一次）</div>
      </div>
      <div>
        <el-button plain @click="exportFile('xlsx')">
          <el-icon><Download /></el-icon>导出 Excel
        </el-button>
        <el-button plain @click="exportFile('csv')">
          <el-icon><Download /></el-icon>导出 CSV
        </el-button>
        <el-button type="primary" @click="router.push('/items/new')">
          <el-icon><Plus /></el-icon>登记新事项
        </el-button>
      </div>
    </div>

    <div class="card">
      <el-form inline label-width="auto" style="row-gap: 8px">
        <el-form-item label="关键词">
          <el-input
            v-model="q"
            placeholder="标题 / 编号 / 单号 / 承办人"
            clearable
            style="width: 200px"
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="category" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="sourceType" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="s in sourceTypes" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="statuses"
            multiple
            collapse-tags
            clearable
            placeholder="全部"
            style="width: 170px"
          >
            <el-option
              v-for="s in statusOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="接收时间">
          <el-date-picker
            v-model="receiveRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="起"
            end-placeholder="止"
            style="width: 220px"
          />
        </el-form-item>
        <el-form-item label="办结时限">
          <el-date-picker
            v-model="dueRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="起"
            end-placeholder="止"
            style="width: 220px"
          />
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="sort" style="width: 120px" @change="search">
            <el-option label="最近登记" value="recent" />
            <el-option label="时限优先" value="due" />
            <el-option label="接收时间" value="receive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="overdue" @change="search">只看超期</el-checkbox>
          <el-checkbox v-model="instruction" @change="search">有领导批示</el-checkbox>
          <el-checkbox v-model="includeMerged" @change="search">含已合并</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
      <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap">
        <span class="muted small">保存的过滤器：</span>
        <el-select
          v-model="selectedFilter"
          clearable
          placeholder="选择筛选方案"
          style="width: 220px"
          @change="applySaved"
        >
          <el-option v-for="f in savedFilters" :key="f.id" :label="f.name" :value="f.id" />
        </el-select>
        <el-button size="small" @click="saveCurrent">保存当前筛选</el-button>
        <el-button size="small" plain type="danger" @click="removeSaved">删除所选</el-button>
      </div>
    </div>

    <div class="card" style="padding: 8px 12px 12px">
      <el-table :data="rows" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="编号" width="125">
          <template #default="{ row }">
            <span class="small muted">{{ row.item_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="事项标题" min-width="230">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 6px">
              <el-icon v-if="row.pinned" color="#e6a23c"><StarFilled /></el-icon>
              <span class="link" @click="router.push(`/items/${row.id}`)">{{ row.title }}</span>
              <el-tag v-if="row.merged_into" size="small" type="info">已合并</el-tag>
              <el-tag v-else-if="row.merged_sources?.length" size="small" type="warning" effect="plain">
                合并{{ row.merged_sources.length }}件
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="100" />
        <el-table-column label="来源" width="140">
          <template #default="{ row }">
            <div>{{ row.source_type }}</div>
            <div class="small muted" v-if="row.source_no">{{ row.source_no }}</div>
          </template>
        </el-table-column>
        <el-table-column label="接收时间" width="150">
          <template #default="{ row }">
            <span class="small">{{ row.receive_time?.replace('T', ' ') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时限" width="140">
          <template #default="{ row }">
            <div class="small">{{ row.due_date || '—' }}</div>
            <el-tag size="small" :type="reminderTag(row).type" effect="plain">
              {{ reminderTag(row).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="105">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="承办人" width="90">
          <template #default="{ row }">{{ row.current_handler || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/items/${row.id}`)">查看</el-button>
            <el-button link @click="togglePin(row)">{{ row.pinned ? '取消置顶' : '置顶' }}</el-button>
            <el-button
              link
              type="danger"
              v-if="!row.merged_into"
              @click="openMerge(row)"
            >
              合并
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display: flex; justify-content: flex-end; margin-top: 12px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </div>

    <el-dialog v-model="mergeDialog" title="合并重复事项" width="520px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="被合并事项的原记录全部保留，仅追加“已合并至”标记，附件随迁，时间线不断链。"
        style="margin-bottom: 14px"
      />
      <el-form label-width="90px">
        <el-form-item label="待合并事项">
          <el-input :model-value="mergeSource ? `${mergeSource.item_no} · ${mergeSource.title}` : ''" disabled />
        </el-form-item>
        <el-form-item label="合并至主事项">
          <ItemPicker v-model="mergeMaster" :exclude-id="mergeSource?.id" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="mergeNote" placeholder="如：同一群众同一诉求的多系统派单" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeDialog = false">取消</el-button>
        <el-button type="primary" :loading="merging" @click="submitMerge">确认合并</el-button>
      </template>
    </el-dialog>
  </div>
</template>
