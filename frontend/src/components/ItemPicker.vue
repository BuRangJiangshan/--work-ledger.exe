<script setup>
import { ref } from 'vue'
import api from '../api'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  excludeId: { type: Number, default: null },
  placeholder: { type: String, default: '输入编号或标题搜索事项' },
})
const emit = defineEmits(['update:modelValue'])
const options = ref([])
const loading = ref(false)

async function search(query) {
  loading.value = true
  try {
    const { data } = await api.get('/api/items', {
      params: { q: query || '', page_size: 20, sort: 'recent' },
    })
    options.value = data.items.filter((item) => item.id !== props.excludeId)
  } finally {
    loading.value = false
  }
}

function onChange(value) {
  emit('update:modelValue', value)
}
</script>

<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    :remote-method="search"
    :loading="loading"
    :placeholder="placeholder"
    style="width: 100%"
    @focus="search('')"
    @change="onChange"
  >
    <el-option
      v-for="item in options"
      :key="item.id"
      :label="`${item.item_no} · ${item.title}`"
      :value="item.id"
    />
  </el-select>
</template>
