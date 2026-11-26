<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { store } from '../store'
import { nowInput } from '../utils'

const router = useRouter()
const formRef = ref()
const saving = ref(false)
const attachments = ref([])

const defaults = () => ({
  title: '',
  category: '综治工单',
  source_type: '综治信息系统',
  source_no: '',
  source_unit: '',
  receive_time: nowInput(),
  receive_method: '系统派单',
  due_type: 'clear',
  estimated_days: null,
  due_date: '',
  handle_mode: 'self',
  current_handler: '',
  pinned: false,
})

const form = reactive(defaults())

const categories = computed(() => store.meta?.categories || [])
const sourceTypes = computed(() => store.meta?.source_types || [])
const receiveMethods = computed(() => store.meta?.receive_methods || [])
const dueTypes = computed(() => store.meta?.due_types || [])
const handleModes = computed(() => store.meta?.handle_modes || [])
const estimateDefaults = computed(() => store.settings?.estimate_defaults || {})

const SOURCE_CATEGORY = {
  综治信息系统: '综治工单',
  信访系统: '信访件',
  群众来电: '群众投诉',
  群众来访: '群众投诉',
  上级交办: '上级交办',
  领导交办: '上级交办',
  会议部署: '会议部署',
  其他: '其他',
}
const SOURCE_METHOD = {
  综治信息系统: '系统派单',
  信访系统: '系统派单',
  群众来电: '电话',
  群众来访: '口头',
  领导交办: '口头',
  上级交办: '文件',
  会议部署: '文件',
}

const workdays = computed(() => {
  const days = Number(form.estimated_days)
  if (!days) return null
  return Math.round((days / 7) * 5)
})

function addDays(base, days) {
  if (!base || days === null || days === undefined || days === '') return ''
  const d = new Date(`${String(base).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  d.setDate(d.getDate() + Number(days))
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function applyCategory(value) {
  const suggestion = estimateDefaults.value[value]
  if (suggestion) {
    form.estimated_days = suggestion
  }
  if (form.due_type === 'clear' && form.estimated_days) {
    form.due_date = addDays(form.receive_time, form.estimated_days)
  }
}

function pickSource(value) {
  form.source_type = value
  if (SOURCE_CATEGORY[value]) {
    form.category = SOURCE_CATEGORY[value]
    applyCategory(form.category)
  }
  if (SOURCE_METHOD[value]) {
    form.receive_method = SOURCE_METHOD[value]
  }
}

function recalcDue() {
  if (form.due_type !== 'clear') {
    form.due_date = ''
    return
  }
  form.due_date = addDays(form.receive_time, form.estimated_days)
}

async function uploadFile(options) {
  const fd = new FormData()
  fd.append('file', options.file)
  try {
    const { data } = await api.post('/api/attachments', fd)
    attachments.value.push({ name: data.name, path: data.path, url: data.url })
    options.onSuccess(data)
  } catch (error) {
    options.onError(error)
  }
}

function removeAttachment(index) {
  attachments.value.splice(index, 1)
}

async function submit(goDetail) {
  if (saving.value) return
  saving.value = true
  try {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) return
    const payload = {
      ...form,
      estimated_days:
        form.estimated_days === null || form.estimated_days === ''
          ? null
          : Number(form.estimated_days),
      due_date: form.due_type === 'none' ? null : form.due_date || null,
      attachments: attachments.value,
    }
    const { data } = await api.post('/api/items', payload)
    ElMessage.success(`登记成功：${data.item_no}`)
    if (goDetail) {
      router.push(`/items/${data.id}`)
    } else {
      Object.assign(form, defaults())
      attachments.value = []
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  } finally {
    saving.value = false
  }
}

function reset() {
  Object.assign(form, defaults())
  attachments.value = []
  formRef.value?.clearValidate()
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">事项登记</h2>
        <div class="page-subtitle">模板化快速登记 · 目标 30 秒录完一条 · 保存后可继续补记细节</div>
      </div>
      <el-button plain @click="reset">重置表单</el-button>
    </div>

    <div class="card">
      <el-form ref="formRef" :model="form" label-width="112px" status-icon>
        <el-form-item
          label="事项标题"
          prop="title"
          :rules="[{ required: true, message: '请填写事项标题', trigger: 'blur' }]"
        >
          <el-input
            v-model="form.title"
            maxlength="120"
            show-word-limit
            placeholder="一句话说清楚：谁、什么事，如“XX社区邻里纠纷工单”"
          />
        </el-form-item>

        <el-form-item label="来源快捷入口">
          <div style="display: flex; flex-wrap: wrap; gap: 8px">
            <el-button
              v-for="s in sourceTypes"
              :key="s"
              size="small"
              :type="form.source_type === s ? 'primary' : 'default'"
              @click="pickSource(s)"
            >
              {{ s }}
            </el-button>
          </div>
        </el-form-item>

        <div class="grid-2">
          <el-form-item
            label="事项类别"
            prop="category"
            :rules="[{ required: true, message: '请选择事项类别', trigger: 'change' }]"
          >
            <el-select v-model="form.category" style="width: 100%" @change="applyCategory">
              <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item
            label="来源类型"
            prop="source_type"
            :rules="[{ required: true, message: '请选择来源类型', trigger: 'change' }]"
          >
            <el-select v-model="form.source_type" style="width: 100%" filterable allow-create>
              <el-option v-for="s in sourceTypes" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源单号">
            <el-input v-model="form.source_no" placeholder="信访编号 / 工单号 / 文号" />
          </el-form-item>
          <el-form-item label="来文来件单位">
            <el-input v-model="form.source_unit" placeholder="如：综治中心、区信访局" />
          </el-form-item>
          <el-form-item
            label="接收时间"
            prop="receive_time"
            :rules="[{ required: true, message: '请选择接收时间', trigger: 'change' }]"
          >
            <el-date-picker
              v-model="form.receive_time"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm"
              format="YYYY-MM-DD HH:mm"
              style="width: 100%"
              @change="recalcDue"
            />
          </el-form-item>
          <el-form-item label="接收方式">
            <el-select v-model="form.receive_method" style="width: 100%" clearable>
              <el-option v-for="m in receiveMethods" :key="m" :label="m" :value="m" />
            </el-select>
          </el-form-item>
        </div>

        <el-divider content-position="left">时限要求</el-divider>

        <div class="grid-3">
          <el-form-item label="时限性质">
            <el-select v-model="form.due_type" style="width: 100%" @change="recalcDue">
              <el-option v-for="d in dueTypes" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="预计办理时长">
            <el-input-number
              v-model="form.estimated_days"
              :min="0"
              :precision="0"
              :controls="false"
              style="width: 100%"
              placeholder="自然日"
              @change="recalcDue"
            />
            <div class="form-tip" v-if="workdays">约 {{ workdays }} 个工作日（仅展示换算）</div>
          </el-form-item>
          <el-form-item label="要求办结时间">
            <el-date-picker
              v-model="form.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              style="width: 100%"
              :disabled="form.due_type === 'none'"
            />
          </el-form-item>
        </div>
        <el-form-item label=" " style="margin-top: -12px">
          <span class="form-tip">
            预计时长按类别默认带出、可覆盖；存储与统计一律使用自然日（信访件默认 60、综治工单 9≈7 个工作日、日常事务 1）。
          </span>
        </el-form-item>

        <el-divider content-position="left">承办与附件</el-divider>

        <div class="grid-3">
          <el-form-item label="办理模式">
            <el-select v-model="form.handle_mode" style="width: 100%">
              <el-option v-for="h in handleModes" :key="h.value" :label="h.label" :value="h.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="当前承办人">
            <el-input v-model="form.current_handler" placeholder="如：王干事" />
          </el-form-item>
          <el-form-item label="置顶">
            <el-switch v-model="form.pinned" />
          </el-form-item>
        </div>

        <el-form-item label="佐证材料">
          <div style="width: 100%">
            <el-upload
              :http-request="uploadFile"
              :show-file-list="false"
              multiple
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt"
            >
              <el-button plain>
                <el-icon><Paperclip /></el-icon>上传照片 / 文件
              </el-button>
            </el-upload>
            <div class="attachments" v-if="attachments.length">
              <el-tag
                v-for="(att, index) in attachments"
                :key="att.path"
                closable
                @close="removeAttachment(index)"
              >
                {{ att.name }}
              </el-tag>
            </div>
            <div class="form-tip">聊天记录截图、通话记录截图、回单等均可作为佐证材料。</div>
          </div>
        </el-form-item>

        <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 8px">
          <el-button @click="router.push('/items')">返回台账</el-button>
          <el-button :loading="saving" @click="submit(false)">保存并继续登记</el-button>
          <el-button type="primary" :loading="saving" @click="submit(true)">保存并查看详情</el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>
