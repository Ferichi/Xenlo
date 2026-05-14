<script setup>
const props = defineProps({
  file: {
    type: File,
    default: null,
  },
})

const emit = defineEmits(['update:file'])

const handleFileChange = (event) => {
  const selectedFile = event.target.files?.[0]

  if (selectedFile) {
    emit('update:file', selectedFile)
  }
}

const clearFile = () => {
  emit('update:file', null)
}

const handleDrop = (event) => {
  event.preventDefault()

  const droppedFile = event.dataTransfer.files?.[0]

  if (droppedFile) {
    emit('update:file', droppedFile)
  }
}

const formatFileSize = (size) => {
  if (!size) return ''

  const sizeInMb = size / 1024 / 1024
  return `${sizeInMb.toFixed(2)} MB`
}
</script>

<template>
  <div class="upload-box" @dragover.prevent @drop="handleDrop">
    <input
      id="file-upload"
      type="file"
      class="file-input"
      accept="audio/*,video/*"
      @change="handleFileChange"
    />

    <div v-if="!props.file" class="upload-empty">
      <i class="pi pi-cloud-upload upload-icon"></i>

      <p class="upload-title">Перетягніть файл сюди</p>
      <p class="upload-subtitle">або оберіть його з пристрою</p>

      <label for="file-upload" class="upload-button">Виберіть файл</label>
    </div>

    <div v-else class="upload-selected">
      <div class="file-info">
        <i class="pi pi-file file-icon"></i>

        <div>
          <p class="file-name">{{ props.file.name }}</p>
          <p class="file-size">{{ formatFileSize(props.file.size) }}</p>
        </div>
      </div>

      <button type="button" class="clear-button" @click="clearFile">Скасувати</button>
    </div>
  </div>
</template>

<style scoped>
.upload-box {
  min-height: 240px;
  border: 1px dashed var(--app-border-strong);
  border-radius: 18px;
  background: var(--app-surface-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.file-input {
  display: none;
}

.upload-empty {
  text-align: center;
  color: var(--app-text-muted);
}

.upload-icon {
  display: block;
  margin-bottom: 14px;
  font-size: 2.5rem;
  color: var(--app-primary);
}

.upload-title {
  margin-bottom: 4px;
  font-weight: 700;
  color: var(--app-text);
}

.upload-subtitle {
  margin-bottom: 18px;
  font-size: 14px;
}

.upload-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 8px 16px;
  border-radius: 10px;
  background: var(--app-primary);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.upload-selected {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: 14px;
  background: #ffffff;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.file-icon {
  color: var(--app-primary);
  font-size: 1.4rem;
}

.file-name {
  font-weight: 700;
  color: var(--app-text);
  word-break: break-word;
}

.file-size {
  color: var(--app-text-muted);
  font-size: 13px;
}

.clear-button {
  border: 1px solid var(--app-border-strong);
  border-radius: 10px;
  background: #ffffff;
  color: var(--app-text);
  padding: 8px 12px;
  cursor: pointer;
}

.clear-button:hover {
  background: #f3f4f6;
}
</style>
