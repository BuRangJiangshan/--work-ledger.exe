<script setup>
import { computed } from 'vue'
import { store } from '../store'

const props = defineProps({ status: { type: String, default: '' } })

const type = computed(() => {
  const color = store.meta?.statuses?.find((s) => s.value === props.status)?.color
  return ['primary', 'success', 'info', 'warning', 'danger'].includes(color) ? color : 'info'
})
const label = computed(
  () => store.meta?.statuses?.find((s) => s.value === props.status)?.label || props.status,
)
</script>

<template>
  <el-tag :type="type" effect="light" round>{{ label }}</el-tag>
</template>
