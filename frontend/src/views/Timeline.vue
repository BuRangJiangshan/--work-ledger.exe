<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import ItemPicker from '../components/ItemPicker.vue'
import { actionColor, fmtDT } from '../utils'
import { store } from '../store'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const types = ref([])
const range = ref([])
const itemId = ref(null)
const limit = ref(100)

const actionTypes = computed(() => store.meta?.action_types || [])

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/timeline', {
      params: {
        types: types.value.length ? types.value.join(',') : undefined,
        start: range.value?.[0] || undefined,
        end: range.value?.[1] || undefined,
        item_id: itemId.value || undefined,
        limit: limit.value,
      },
    })
    rows.value = data
  } finally {
    loading.value = false
  }
}

function reset() {
  types.value = []
  range.value = []
  itemId.value = null
  load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2 class="page-title">全局时间线</h2>
        <div class="page-subtitle">所有事项的所有动作事件按时间倒序聚合，共 {{ rows.length }} 条</div>
      </div>
      <el-button plain @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
    </div>

    <div class="card">
      <el-form inline label-width="auto" style="row-gap: 8px">
        <el-form-item label="事件类型">
          <el-select
            v-model="types"
            multiple
            collapse-tags
            clearable
            placeholder="全部事件"
            style="width: 240px"
            @change="load"
          >
            <el-option v-for="a in actionTypes" :key="a.value" :label="a.label" :value="a.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="range"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="起"
            end-placeholder="止"
            style="width: 230px"
            @change="load"
          />
        </el-form-item>
        <el-form-item label="指定事项">
          <div style="width: 260px">
            <ItemPicker v-model="itemId" @update:model-value="load" />
          </div>
        </el-form-item>
        <el-form-item label="条数">
          <el-select v-model="limit" style="width: 100px" @change="load">
            <el-option :value="50" label="50 条" />
            <el-option :value="100" label="100 条" />
            <el-option :value="200" label="200 条" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="card">
      <el-empty v-if="!rows.length" description="暂无事件记录" />
      <el-timeline v-else>
        <el-timeline-item
          v-for="rec in rows"
          :key="rec.id"
          :timestamp="fmtDT(rec.action_time)"
          placement="top"
          :color="actionColor(rec.action_type)"
        >
          <div class="timeline-item-head">
            <el-tag size="small" :color="actionColor(rec.action_type)" style="color: #fff; border: none">
              {{ rec.action_label }}
            </el-tag>
            <span class="link" @click="router.push(`/items/${rec.item_id}`)">
              {{ rec.item_no }} · {{ rec.item_title }}
            </span>
            <el-tag size="small" effect="plain">{{ rec.item_status_label }}</el-tag>
            <span v-if="rec.report_channels?.length" class="small muted">
              渠道：{{ rec.report_channels.join('、') }}
            </span>
            <span v-if="rec.target_person" class="small muted">对象：{{ rec.target_person }}</span>
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
  </div>
</template>
