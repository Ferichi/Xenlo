<script setup>
import Button from 'primevue/button'

defineProps({
  label: {
    type: String,
    required: true,
  },
  variant: {
    type: String,
    default: 'primary', // primary | secondary | text
  },
  icon: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  fluid: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <Button
    :label="label"
    :icon="icon || undefined"
    :disabled="disabled"
    :fluid="fluid"
    :severity="variant === 'secondary' ? 'secondary' : undefined"
    :variant="variant === 'text' ? 'text' : undefined"
    class="app-button"
  />
</template>

<style scoped>
.app-button {
  font-weight: 600;
}
</style>
