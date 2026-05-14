<script setup>
import Select from 'primevue/select'

defineProps({
  modelValue: {
    type: [String, Object, Number, null],
    default: null,
  },
  options: {
    type: Array,
    default: () => [],
  },
  optionLabel: {
    type: String,
    default: undefined,
  },
  placeholder: {
    type: String,
    default: 'Оберіть значення',
  },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <Select
    :modelValue="modelValue"
    :options="options"
    :optionLabel="optionLabel"
    :placeholder="placeholder"
    class="app-select"
    @update:modelValue="$emit('update:modelValue', $event)"
  />
</template>

<style scoped>
.app-select {
  width: 100%;
}
</style>
