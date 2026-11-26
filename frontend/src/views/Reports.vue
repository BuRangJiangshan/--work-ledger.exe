<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { downloadBlob } from '../api'
import { monthRange, todayStr } from '../utils'
import { store } from '../store'

const route = useRoute()
const templates = ref([])
const templateId = ref(null)
const range = ref(monthRange())
const organize = ref('category')
const report = ref(null)
const loading = ref(false)
const previewing = ref(false)

const customDialog = ref(false)
const customName = ref('')
const customHeadings = ref('一、重点工作进展情况\n二、信访件及群众诉求办理情况\n三、其他事项')

const currentTemplate = computed(() => templates.value.find((t) => t.id === templateId.value))

async function loadTemplates() {
  const { data } = await api.get('/api/report-templates')
  templates.value = data
  if (!templateId.value) {
    const builtin = data.find((t) => t.source === 'builtin')
    templateId.value = builtin?.id || data[0]?.id || null
  }
}

function payload() {
  return {
    template_id: templateId.value,
    start: range.value?.[0] || null,
    end: range.value?.[1] || null,
    organize: organize.value,
  }
}

async function preview() {
  if (!range.value?.length) {
    ElMessage.warning('请选择汇报时间范围')
    return
  }
  previewing.value = true
  try {
    const { data } = await api.post('/api/reports/preview', payload())
    report.value = data
  } finally {
    previewing.value = false
  }
}

async function exportWord() {
  if (!report.value) {
    await preview()
  }
  if (!report.value) return
  loading.value = true
  try {
    const filename = `${report.value.title}_${range.value?.[0] || ''}_${range.value?.[1] || ''}.docx`
    await downloadBlob(api.post('/api/reports/export', payload(), { responseType: 'blob' }), filename)
    ElMessage.success('Word 已导出')
  } finally {
    loading.value = false
  }
}

async function createCustom() {
  const headings = customHeadings.value.split('\n').map((h) => h.trim()).filter(Boolean)
  if (!customName.value.trim() || !headings.length) {
    ElMessage.warning('请填写模板名称和分类标题')
    return
  }
  const { data } = await api.post('/api/report-templates', {
    name: customName.value.trim(),
    headings,
  })
  ElMessage.success('自定义模板已创建')
  customDialog.value = false
  await loadTemplates()
  templateId.value = data.id
}

async function importFile(options) {
  const fd = new FormData()
  fd.append('file', options.file)
  try {
    const { data } = await api.post('/api/report-templates/import', fd)
    options.onSuccess(data)
    ElMessage.success(`已导入模板：${data.name}`)
    await loadTemplates()
    templateId.value = data.id
  } catch (error) {
    options.onError(error)
  }
}

async function removeTemplate(template) {
  try {
    await ElMessageBox.confirm(`确定删除模板「${template.name}」？`, '提示', { type: 'warning' })
    await api.delete(`/api/report-templates/${template.id}`)
    if (templateId.value === template.id) templateId.value = null
    await loadTemplates()
    report.value = null
    ElMessage.success('已删除')
  } catch (error) {
    /* 取消 */
  }
}

onMounted(async () => {
  if (route.query.start && route.query.end) {
    range.value = [String(route.query.start), String(route.query.end)]
  }
  await loadTemplates()
  if (range.value?.length) preview()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="page-title">汇报中心</h2>
        <div class="page-subtitle">
          选模板 + 选时间范围 → 自动生成初稿 → 人工微调 → 导出 Word（单位名称可在设置中填写）
        </div>
      </div>
      <span class="muted small">
        单位名称：{{ store.settings?.unit_name || '未设置（可在设置中填写）' }}
      </span>
    </div>

    <div class="card">
      <el-form label-width="96px">
        <el-form-item label="汇报模板">
          <div style="display: flex; gap: 10px; flex-wrap: wrap; width: 100%">
            <el-select v-model="templateId" style="width: 320px" @change="report = null">
              <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-button @click="customDialog = true">新建自定义模板</el-button>
            <el-upload
              :http-request="importFile"
              :show-file-list="false"
              accept=".docx,.xlsx"
            >
              <el-button>导入单位样例（Word/Excel）</el-button>
            </el-upload>
            <el-button
              v-if="currentTemplate && !currentTemplate.builtin"
              type="danger"
              plain
              @click="removeTemplate(currentTemplate)"
            >
              删除当前模板
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="range"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 300px"
            @change="report = null"
          />
        </el-form-item>
        <el-form-item label="组织方式">
          <el-radio-group v-model="organize" @change="report = null">
            <el-radio value="category">分类别汇总</el-radio>
            <el-radio value="status">已完成 / 进行中 / 待办</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="模板结构">
          <div class="small muted">
            <template v-if="currentTemplate">
              <el-tag
                v-for="h in currentTemplate.structure?.headings || []"
                :key="h"
                size="small"
                style="margin-right: 6px; margin-bottom: 4px"
              >
                {{ h }}
              </el-tag>
            </template>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="previewing" @click="preview">生成初稿</el-button>
          <el-button :loading="loading" :disabled="!report" @click="exportWord">导出 Word</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card">
      <div class="card-title">
        汇报初稿
        <span class="count" v-if="report">
          {{ report.item_count }} 件事项 · 已办结 {{ report.finished_count }} 件 · {{ report.template_name }}
        </span>
      </div>
      <el-empty v-if="!report" description="选择模板和时间范围后点击“生成初稿”" />
      <div v-else class="report-paper">
        <div class="report-preview-title">{{ report.title }}</div>
        <div class="report-preview-sub">{{ report.subtitle }}</div>
        <div style="margin-bottom: 14px">{{ report.summary_line }}</div>
        <div v-for="section in report.sections" :key="section.heading">
          <div style="font-weight: 700; margin: 14px 0 6px">{{ section.heading }}</div>
          <p
            v-for="(line, idx) in section.lines"
            :key="idx"
            style="margin: 4px 0; text-indent: 2em"
          >
            {{ line }}
          </p>
          <p v-if="!section.lines.length" class="muted" style="margin: 4px 0 4px 2em">
            本项无事项。
          </p>
        </div>
      </div>
    </div>

    <el-dialog v-model="customDialog" title="新建自定义汇报模板" width="560px">
      <el-form label-width="96px">
        <el-form-item label="模板名称">
          <el-input v-model="customName" placeholder="如：单位周报模板" />
        </el-form-item>
        <el-form-item label="分类标题">
          <el-input
            v-model="customHeadings"
            type="textarea"
            :rows="6"
            placeholder="每行一个分类标题"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="customDialog = false">取消</el-button>
        <el-button type="primary" @click="createCustom">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
