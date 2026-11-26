<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import StatusTag from '../components/StatusTag.vue'
import ItemPicker from '../components/ItemPicker.vue'
import { actionColor, fmtDT, nowInput, reminderTag } from '../utils'
import { store } from '../store'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const item = ref(null)

const actionTypes = computed(() => store.meta?.action_types || [])
const categories = computed(() => store.meta?.categories || [])
const sourceTypes = computed(() => store.meta?.source_types || [])
const dueTypes = computed(() => store.meta?.due_types || [])
const finishMethods = computed(() => store.meta?.finish_methods || [])
const reportChannels = computed(() => store.meta?.report_channels || [])
const relationTypes = computed(() => store.meta?.relation_types || [])
const handleModes = computed(() => store.meta?.handle_modes || [])

const FIELD_LABEL = {
  status: '状态',
  due_date: '要求办结时间',
  original_due_date: '原要求办结时间',
  current_handler: '当前承办人',
  finish_time: '办结时间',
  finish_method: '办结方式',
  finish_summary: '结果摘要',
  actual_days: '实际用时',
  delay_reason: '延期原因',
  delay_applied_to: '向谁申请延期',
  delay_approved: '延期批准',
  pinned: '置顶',
  title: '标题',
  handle_mode: '办理模式',
  merged_into: '合并去向',
  merged_from: '合并来源',
  created: '创建',
}

const recordDialog = ref(false)
const recordForm = reactive({
  action_type: 'progress',
  content: '',
  report_to: '',
  target_person: '',
  report_channels: [],
  leader_opinion: '',
  finish_method: '',
  finish_summary: '',
  delay_reason: '',
  delay_applied_to: '',
  action_time: nowInput(),
  attachments: [],
})

const editDialog = ref(false)
const editForm = reactive({})

const delayDialog = ref(false)
const delayForm = reactive({ approved: true, due_date: '' })

const relationDialog = ref(false)
const relationForm = reactive({ relation_type: 'related', related_item_id: null, note: '' })

const mergeDialog = ref(false)
const mergeMaster = ref(null)
const mergeNote = ref('')

const reportDialog = ref(false)
const itemReport = ref(null)

const submitting = ref(false)

const isMerged = computed(() => !!item.value?.merged_into)
const showDelayApproval = computed(
  () => item.value && item.value.delay_approved === 0 && item.value.delay_reason,
)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/api/items/${route.params.id}`)
    item.value = data
  } finally {
    loading.value = false
  }
}

function resetRecord(action) {
  Object.assign(recordForm, {
    action_type: action,
    content: '',
    report_to: '',
    target_person: '',
    report_channels: [],
    leader_opinion: '',
    finish_method: '',
    finish_summary: '',
    delay_reason: '',
    delay_applied_to: '',
    action_time: nowInput(),
    attachments: [],
  })
}

function openRecord(action = 'progress') {
  if (isMerged.value) {
    ElMessage.warning('该事项已合并，请在主事项上补记过程')
    return
  }
  resetRecord(action)
  recordDialog.value = true
}

async function uploadRecordFile(options) {
  const fd = new FormData()
  fd.append('file', options.file)
  try {
    const { data } = await api.post('/api/attachments', fd)
    recordForm.attachments.push({ name: data.name, path: data.path, url: data.url })
    options.onSuccess(data)
  } catch (error) {
    options.onError(error)
  }
}

async function submitRecord() {
  const action = recordForm.action_type
  if (!recordForm.content.trim() && action !== 'finish') {
    ElMessage.warning('请填写内容描述')
    return
  }
  if (action === 'finish' && !recordForm.finish_method) {
    ElMessage.warning('办结必须选择办结方式')
    return
  }
  if (action === 'delay' && (!recordForm.delay_reason || !recordForm.delay_applied_to)) {
    ElMessage.warning('延期必须填写原因和申请对象')
    return
  }
  if (action === 'assign' && !recordForm.target_person) {
    ElMessage.warning('请填写交办对象')
    return
  }
  const payload = {
    action_type: action,
    content: recordForm.content,
    action_time: recordForm.action_time,
    report_to: recordForm.report_to || null,
    target_person: recordForm.target_person || null,
    report_channels: recordForm.report_channels,
    leader_opinion: recordForm.leader_opinion || null,
    attachments: recordForm.attachments,
    finish_method: recordForm.finish_method || null,
    finish_summary: recordForm.finish_summary || null,
    delay_reason: recordForm.delay_reason || null,
    delay_applied_to: recordForm.delay_applied_to || null,
  }
  submitting.value = true
  try {
    const { data } = await api.post(`/api/items/${item.value.id}/records`, payload)
    recordDialog.value = false
    item.value = data.item
    ElMessage.success('过程记录已保存')
    if (data.warnings?.length) {
      ElMessageBox.alert(
        data.warnings.map((w) => w.message).join('；') + '。请确认是否仍需办结。',
        '办结提醒',
        { type: 'warning' },
      )
    }
  } finally {
    submitting.value = false
  }
}

function openEdit() {
  const source = item.value
  Object.assign(editForm, {
    title: source.title,
    category: source.category,
    source_type: source.source_type,
    source_no: source.source_no,
    source_unit: source.source_unit,
    receive_time: source.receive_time,
    receive_method: source.receive_method,
    due_date: source.due_date,
    due_type: source.due_type,
    estimated_days: source.estimated_days,
    handle_mode: source.handle_mode,
    current_handler: source.current_handler,
  })
  editDialog.value = true
}

async function submitEdit() {
  submitting.value = true
  try {
    const { data } = await api.patch(`/api/items/${item.value.id}`, { ...editForm })
    item.value = data
    editDialog.value = false
    ElMessage.success('已保存，变更已写入审计历史')
  } finally {
    submitting.value = false
  }
}

function openDelay() {
  delayForm.approved = true
  delayForm.due_date = item.value.due_date || ''
  delayDialog.value = true
}

async function submitDelay() {
  const payload = { delay_approved: delayForm.approved ? 1 : 0 }
  if (delayForm.approved) {
    if (!delayForm.due_date) {
      ElMessage.warning('批准延期需填写新时限')
      return
    }
    payload.due_date = delayForm.due_date
  }
  submitting.value = true
  try {
    const { data } = await api.patch(`/api/items/${item.value.id}`, payload)
    item.value = data
    delayDialog.value = false
    ElMessage.success('延期审批结果已记录')
  } finally {
    submitting.value = false
  }
}

async function togglePin() {
  const { data } = await api.post(`/api/items/${item.value.id}/pin`, {
    pinned: !item.value.pinned,
  })
  item.value = data
}

function openRelation() {
  Object.assign(relationForm, { relation_type: 'related', related_item_id: null, note: '' })
  relationDialog.value = true
}

async function submitRelation() {
  if (!relationForm.related_item_id) {
    ElMessage.warning('请选择关联事项')
    return
  }
  await api.post('/api/relations', {
    master_item_id: item.value.id,
    related_item_id: relationForm.related_item_id,
    relation_type: relationForm.relation_type,
    note: relationForm.note,
  })
  relationDialog.value = false
  ElMessage.success('关系已建立')
  load()
}

async function deleteRelation(relation) {
  try {
    await ElMessageBox.confirm('确定删除该关联关系？此操作会写入审计历史。', '提示', {
      type: 'warning',
    })
    await api.delete(`/api/relations/${relation.id}`)
    ElMessage.success('已删除')
    load()
  } catch (error) {
    /* 取消 */
  }
}

async function submitMerge() {
  if (!mergeMaster.value) {
    ElMessage.warning('请选择主事项')
    return
  }
  submitting.value = true
  try {
    const { data } = await api.post(`/api/items/${item.value.id}/merge`, {
      master_id: mergeMaster.value,
      note: mergeNote.value,
    })
    ElMessage.success(`已合并到 ${data.item_no}`)
    mergeDialog.value = false
    router.push(`/items/${data.id}`)
  } finally {
    submitting.value = false
  }
}

async function openReport() {
  const { data } = await api.get(`/api/reports/items/${item.value.id}/preview`)
  itemReport.value = data
  reportDialog.value = true
}

function downloadItemReport() {
  window.open(`/api/reports/items/${item.value.id}/export`, '_blank')
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <template v-if="item">
      <div class="detail-hero">
        <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
          <div>
            <span class="hero-tag">{{ item.item_no }}</span>
            <span class="hero-tag" v-if="item.category">{{ item.category }}</span>
            <span class="hero-tag" v-if="item.source_type">{{ item.source_type }}</span>
            <h2>{{ item.title }}</h2>
            <div class="meta">
              <span>接收：{{ fmtDT(item.receive_time) }}</span>
              <span>要求办结：{{ item.due_date || '无明确时限' }}</span>
              <span v-if="item.current_handler">承办人：{{ item.current_handler }}</span>
              <span>状态：{{ item.status_label }}</span>
              <span v-if="item.remaining_days !== null && item.status !== 'finished'">
                {{
                  item.remaining_days < 0
                    ? `已超期 ${Math.abs(item.remaining_days)} 天`
                    : `剩余 ${item.remaining_days} 天`
                }}
              </span>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-end">
            <StatusTag :status="item.status" />
            <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end">
              <el-button size="small" plain @click="togglePin">
                <el-icon><StarFilled /></el-icon>{{ item.pinned ? '取消置顶' : '置顶' }}
              </el-button>
              <el-button size="small" plain @click="openEdit">编辑信息</el-button>
              <el-button size="small" plain @click="openReport">办理报告</el-button>
              <el-button size="small" type="primary" @click="openRecord('progress')">
                补记过程
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <el-alert
        v-if="item.merged_into_item"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
        :title="`该事项已合并至主事项 ${item.merged_into_item.item_no}「${item.merged_into_item.title}」，原记录全部保留。`"
      >
        <el-button link type="primary" @click="router.push(`/items/${item.merged_into_item.id}`)">
          前往主事项查看时间线
        </el-button>
      </el-alert>

      <div class="card">
        <div class="card-title">基本信息</div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="来源类型">{{ item.source_type }}</el-descriptions-item>
          <el-descriptions-item label="来源单号">{{ item.source_no || '—' }}</el-descriptions-item>
          <el-descriptions-item label="来文单位">{{ item.source_unit || '—' }}</el-descriptions-item>
          <el-descriptions-item label="接收时间">{{ fmtDT(item.receive_time) }}</el-descriptions-item>
          <el-descriptions-item label="接收方式">{{ item.receive_method || '—' }}</el-descriptions-item>
          <el-descriptions-item label="办理模式">
            {{ item.handle_mode === 'assigned' ? '交办他人' : '本人办理' }}
          </el-descriptions-item>
          <el-descriptions-item label="要求办结">{{ item.due_date || '无明确时限' }}</el-descriptions-item>
          <el-descriptions-item label="时限性质">
            {{ dueTypes.find((d) => d.value === item.due_type)?.label || item.due_type }}
          </el-descriptions-item>
          <el-descriptions-item label="预计办理时长">
            {{ item.estimated_days ?? '—' }} 个自然日
          </el-descriptions-item>
          <el-descriptions-item label="办结时间">{{ fmtDT(item.finish_time) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="办结方式">{{ item.finish_method || '—' }}</el-descriptions-item>
          <el-descriptions-item label="实际用时">
            {{ item.actual_days ?? '—' }} 个自然日
            <span
              v-if="item.actual_days !== null && item.estimated_days !== null"
              class="muted small"
            >
              （偏差 {{ (item.actual_days - item.estimated_days).toFixed(0) }} 天）
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="结果摘要" :span="3">
            {{ item.finish_summary || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="延期原因" :span="2">
            {{ item.delay_reason || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="延期状态">
            <el-tag
              v-if="item.delay_approved === 1"
              type="warning"
              size="small"
            >已批准（新时限 {{ item.due_date }}）</el-tag>
            <el-tag v-else-if="item.delay_approved === 0" type="danger" size="small">未批准</el-tag>
            <span v-else class="muted">未申请</span>
          </el-descriptions-item>
          <el-descriptions-item label="附件" :span="3">
            <div class="attachments" v-if="item.attachments?.length">
              <a
                v-for="att in item.attachments"
                :key="att.path"
                class="attachment-link"
                :href="att.url"
                target="_blank"
              >
                {{ att.name }}
              </a>
            </div>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 12px" v-if="showDelayApproval">
          <el-button type="warning" size="small" @click="openDelay">办理延期审批</el-button>
        </div>
      </div>

      <div class="card">
        <div class="card-title" style="justify-content: space-between">
          <span>
            关联事项
            <span class="count">{{ item.relations.length + item.merged_sources.length }} 条</span>
          </span>
          <div>
            <el-button size="small" @click="openRelation">添加关联</el-button>
            <el-button
              v-if="!isMerged"
              size="small"
              plain
              type="danger"
              @click="mergeMaster = null; mergeNote = ''; mergeDialog = true"
            >
              合并到其他事项
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="item.merged_sources.length"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 10px"
          :title="`已合并 ${item.merged_sources.length} 个重复事项：${item.merged_sources.map((m) => m.item_no).join('、')}`"
        />
        <div v-if="!item.relations.length && !item.merged_sources.length" class="muted small">
          暂无关联事项。重复信访、多系统派单、口头交办+正式来文可在此建立关系或合并。
        </div>
        <div v-for="rel in item.relations" :key="rel.id" class="item-row">
          <el-tag size="small" :type="rel.relation_type === 'duplicate' ? 'danger' : rel.relation_type === 'parent_child' ? 'warning' : 'info'">
            {{ rel.relation_label }}
          </el-tag>
          <span class="small muted">{{ rel.direction === 'master' ? '主 → 从' : '从 → 主' }}</span>
          <span class="title" @click="router.push(`/items/${rel.other.id}`)">
            {{ rel.other.item_no }} · {{ rel.other.title }}
          </span>
          <span class="small muted">{{ rel.note }}</span>
          <el-button link type="danger" size="small" @click="deleteRelation(rel)">删除</el-button>
        </div>
      </div>

      <div class="card">
        <div class="card-title" style="justify-content: space-between">
          <span>办理时间线 <span class="count">{{ item.records.length }} 条</span></span>
          <div style="display: flex; gap: 6px; flex-wrap: wrap">
            <el-button v-for="a in actionTypes" :key="a.value" size="small" plain @click="openRecord(a.value)">
              {{ a.label }}
            </el-button>
          </div>
        </div>

        <el-empty v-if="!item.records.length" description="暂无过程记录，点击上方按钮补记" />
        <el-timeline v-else class="timeline-wrap">
          <el-timeline-item
            v-for="rec in item.records"
            :key="rec.id"
            :timestamp="fmtDT(rec.action_time)"
            placement="top"
            :color="actionColor(rec.action_type)"
          >
            <div class="timeline-item-head">
              <el-tag size="small" :color="actionColor(rec.action_type)" style="color: #fff; border: none">
                {{ rec.action_label }}
              </el-tag>
              <span v-if="rec.report_channels?.length" class="small muted">
                渠道：{{ rec.report_channels.join('、') }}
              </span>
              <span v-if="rec.report_to" class="small muted">汇报对象：{{ rec.report_to }}</span>
              <span v-if="rec.target_person" class="small muted">对象：{{ rec.target_person }}</span>
              <span v-if="rec.origin_item_no" class="small muted">
                原事项：{{ rec.origin_item_no }}
              </span>
            </div>
            <div class="timeline-content">{{ rec.content }}</div>
            <div v-if="rec.leader_opinion" class="opinion-box">
              <strong>领导批示：</strong>{{ rec.leader_opinion }}
            </div>
            <div class="attachments" v-if="rec.attachments?.length">
              <a
                v-for="att in rec.attachments"
                :key="att.path"
                class="attachment-link"
                :href="att.url"
                target="_blank"
              >
                {{ att.name }}
              </a>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <el-collapse>
        <el-collapse-item :title="`审计历史（${item.audit.length} 条，追加写入，不可篡改）`" name="audit">
          <el-table :data="item.audit" size="small" stripe max-height="360">
            <el-table-column label="操作时间" width="160">
              <template #default="{ row }">{{ fmtDT(row.op_time) }}</template>
            </el-table-column>
            <el-table-column label="对象" width="120">
              <template #default="{ row }">
                {{ row.obj_type === 'item' ? '事项' : row.obj_type === 'process_record' ? '过程记录' : row.obj_type === 'relation' ? '关联关系' : row.obj_type }}
              </template>
            </el-table-column>
            <el-table-column label="字段" width="130">
              <template #default="{ row }">{{ FIELD_LABEL[row.field_name] || row.field_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="旧值" min-width="150">
              <template #default="{ row }">{{ row.old_value ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="新值" min-width="180">
              <template #default="{ row }">{{ row.new_value ?? '—' }}</template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <el-dialog v-model="recordDialog" title="补记过程记录" width="620px" destroy-on-close>
        <el-form label-width="96px">
          <el-form-item label="动作类型">
            <el-select v-model="recordForm.action_type" style="width: 100%">
              <el-option v-for="a in actionTypes" :key="a.value" :label="a.label" :value="a.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="动作时间">
            <el-date-picker
              v-model="recordForm.action_time"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm"
              format="YYYY-MM-DD HH:mm"
              style="width: 100%"
            />
            <div class="form-tip">默认自动打戳；补录历史动作时可调整。</div>
          </el-form-item>
          <el-form-item label="内容描述" required>
            <el-input
              v-model="recordForm.content"
              type="textarea"
              :rows="3"
              placeholder="做了什么、反馈了什么（办结动作可填结果摘要）"
            />
          </el-form-item>

          <template v-if="recordForm.action_type === 'report'">
            <el-form-item label="汇报渠道">
              <el-checkbox-group v-model="recordForm.report_channels">
                <el-checkbox v-for="c in reportChannels" :key="c" :value="c" :label="c">
                  {{ c }}
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="汇报对象">
              <el-input v-model="recordForm.report_to" placeholder="如：张主任" />
            </el-form-item>
          </template>

          <el-form-item v-if="recordForm.action_type === 'instruction'" label="领导批示原文">
            <el-input
              v-model="recordForm.leader_opinion"
              type="textarea"
              :rows="2"
              placeholder="批示原文照记，便于专项统计"
            />
          </el-form-item>

          <el-form-item
            v-if="['assign', 'urge'].includes(recordForm.action_type)"
            :label="recordForm.action_type === 'assign' ? '交办对象' : '催办对象'"
          >
            <el-input v-model="recordForm.target_person" placeholder="姓名" />
          </el-form-item>

          <template v-if="recordForm.action_type === 'finish'">
            <el-form-item label="办结方式" required>
              <el-select v-model="recordForm.finish_method" style="width: 100%">
                <el-option v-for="m in finishMethods" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="结果摘要">
              <el-input v-model="recordForm.finish_summary" type="textarea" :rows="2" />
            </el-form-item>
          </template>

          <template v-if="recordForm.action_type === 'delay'">
            <el-form-item label="延期原因" required>
              <el-input v-model="recordForm.delay_reason" placeholder="如：当事人外出，需重新约定时间" />
            </el-form-item>
            <el-form-item label="向谁申请" required>
              <el-input v-model="recordForm.delay_applied_to" placeholder="如：张主任" />
            </el-form-item>
          </template>

          <el-form-item label="佐证材料">
            <el-upload :http-request="uploadRecordFile" :show-file-list="false" multiple>
              <el-button size="small" plain>
                <el-icon><Paperclip /></el-icon>上传
              </el-button>
            </el-upload>
            <div class="attachments" v-if="recordForm.attachments.length">
              <el-tag
                v-for="(att, idx) in recordForm.attachments"
                :key="att.path"
                closable
                @close="recordForm.attachments.splice(idx, 1)"
              >
                {{ att.name }}
              </el-tag>
            </div>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="recordDialog = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitRecord">保存记录</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="editDialog" title="编辑事项信息" width="640px">
        <el-form label-width="100px">
          <el-form-item label="事项标题">
            <el-input v-model="editForm.title" />
          </el-form-item>
          <div class="grid-2">
            <el-form-item label="事项类别">
              <el-select v-model="editForm.category" style="width: 100%">
                <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
            <el-form-item label="来源类型">
              <el-select v-model="editForm.source_type" style="width: 100%">
                <el-option v-for="s in sourceTypes" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="来源单号">
              <el-input v-model="editForm.source_no" />
            </el-form-item>
            <el-form-item label="来文单位">
              <el-input v-model="editForm.source_unit" />
            </el-form-item>
            <el-form-item label="接收时间">
              <el-date-picker
                v-model="editForm.receive_time"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm"
                format="YYYY-MM-DD HH:mm"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="要求办结">
              <el-date-picker
                v-model="editForm.due_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="时限性质">
              <el-select v-model="editForm.due_type" style="width: 100%">
                <el-option v-for="d in dueTypes" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="预计时长">
              <el-input-number
                v-model="editForm.estimated_days"
                :min="0"
                :controls="false"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="办理模式">
              <el-select v-model="editForm.handle_mode" style="width: 100%">
                <el-option v-for="h in handleModes" :key="h.value" :label="h.label" :value="h.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="当前承办人">
              <el-input v-model="editForm.current_handler" />
            </el-form-item>
          </div>
          <div class="form-tip">所有字段变更都会追加写入审计历史。</div>
        </el-form>
        <template #footer>
          <el-button @click="editDialog = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitEdit">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="delayDialog" title="延期审批" width="460px">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          :title="`申请对象：${item.delay_applied_to || '—'}；原因：${item.delay_reason || '—'}`"
          style="margin-bottom: 14px"
        />
        <el-form label-width="90px">
          <el-form-item label="审批结果">
            <el-radio-group v-model="delayForm.approved">
              <el-radio :value="true">批准</el-radio>
              <el-radio :value="false">不批准</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="delayForm.approved" label="新办结时限" required>
            <el-date-picker
              v-model="delayForm.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="delayDialog = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitDelay">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="relationDialog" title="添加关联事项" width="520px">
        <el-form label-width="90px">
          <el-form-item label="关系类型">
            <el-select v-model="relationForm.relation_type" style="width: 100%">
              <el-option v-for="r in relationTypes" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联事项">
            <ItemPicker v-model="relationForm.related_item_id" :exclude-id="item.id" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="relationForm.note" placeholder="关系说明" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="relationDialog = false">取消</el-button>
          <el-button type="primary" @click="submitRelation">确定</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="mergeDialog" title="合并到主事项" width="520px">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="被合并事项的原记录全部保留，附件随迁，时间线注明原事项编号。"
          style="margin-bottom: 14px"
        />
        <el-form label-width="90px">
          <el-form-item label="合并至">
            <ItemPicker v-model="mergeMaster" :exclude-id="item.id" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="mergeNote" placeholder="如：同一事项多来源派单" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="mergeDialog = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitMerge">确认合并</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="reportDialog" title="单事项办理报告" width="760px">
        <div v-if="itemReport" class="report-paper" style="max-height: 55vh">{{ itemReport.text }}</div>
        <template #footer>
          <el-button @click="reportDialog = false">关闭</el-button>
          <el-button type="primary" @click="downloadItemReport">导出 Word</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>
