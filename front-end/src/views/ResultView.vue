<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import Card from 'primevue/card'
import AppButton from '../components/ui/AppButton.vue'
import { getTranscriptionById } from '../services/transcription-storage.service'

const route = useRoute()

const transcription = ref(null)
const editorRef = ref(null)

const fileName = computed(() => transcription.value?.fileName || 'Результат транскрибації')
const fileStatus = computed(() => transcription.value?.status || 'Очікування')
const fileDate = computed(() => transcription.value?.date || '—')
const audioUrl = computed(() => transcription.value?.audioUrl || '')

const resultText = computed(() => {
  const result = transcription.value?.result

  if (!result) {
    return 'Результат транскрибації з’явиться тут після завершення обробки.'
  }

  if (result.overall_text) {
    return result.overall_text
  }

  if (Array.isArray(result.segments)) {
    return result.segments
      .map((segment) => {
        const speaker = segment.speaker || segment.speaker_label || 'Спікер'
        const text = segment.text || ''
        const start = typeof segment.start === 'number' ? `[${segment.start.toFixed(1)}с] ` : ''

        return `${start}${speaker}:\n${text}`
      })
      .join('\n\n')
  }

  return 'Результат отримано, але формат відповіді не вдалося розпізнати.'
})

const applyFormat = (command) => {
  editorRef.value?.focus()
  document.execCommand(command, false, null)
}

const safeFileName = computed(() => {
  return fileName.value.replace(/[\\/:*?"<>|]/g, '_')
})

const downloadTXT = () => {
  const text = editorRef.value?.innerText || ''

  const blob = new Blob([text], {
    type: 'text/plain;charset=utf-8',
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `${safeFileName.value}.txt`
  link.click()

  URL.revokeObjectURL(url)
}

const downloadJSON = () => {
  const data = transcription.value?.result || {
    message: 'Результат ще не доступний',
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json;charset=utf-8',
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `${safeFileName.value}.json`
  link.click()

  URL.revokeObjectURL(url)
}

const downloadPDF = () => {
  window.print()
}

onMounted(() => {
  const id = route.query.id

  if (id) {
    transcription.value = getTranscriptionById(id)
  }

  if (editorRef.value) {
    editorRef.value.innerText = resultText.value
  }
})
</script>

<template>
  <div class="container result-view">
    <Card class="result-card">
      <template #content>
        <div class="result-header">
          <h1 class="result-title">{{ fileName }}</h1>

          <div class="result-meta">
            <span>Статус: {{ fileStatus }}</span>
            <span>Дата: {{ fileDate }}</span>
          </div>
        </div>

        <div class="result-layout">
          <div class="result-main">
            <div class="player-block">
              <div class="block-title">Аудіоплеєр</div>

              <audio v-if="audioUrl" controls class="audio-player" :src="audioUrl">
                Ваш браузер не підтримує аудіо елемент.
              </audio>

              <div v-else class="audio-empty">
                Аудіоплеєр буде доступний після того, як бекенд поверне посилання на аудіофайл.
              </div>
            </div>

            <div class="editor-block">
              <div class="editor-header">
                <div class="block-title">Редактор тексту</div>

                <div class="editor-toolbar">
                  <button type="button" class="tool-button" @click="applyFormat('bold')">
                    <b>B</b>
                  </button>
                  <button type="button" class="tool-button" @click="applyFormat('italic')">
                    <i>I</i>
                  </button>
                  <button type="button" class="tool-button" @click="applyFormat('underline')">
                    <u>U</u>
                  </button>
                  <button type="button" class="tool-button" @click="applyFormat('removeFormat')">
                    Очистити
                  </button>
                </div>
              </div>

              <div ref="editorRef" class="editor-area" contenteditable="true"></div>
            </div>
          </div>

          <aside class="export-panel">
            <div class="export-title">Експорт</div>

            <div class="export-buttons">
              <AppButton label="TXT" variant="secondary" @click="downloadTXT" />
              <AppButton label="JSON" variant="secondary" @click="downloadJSON" />
              <AppButton label="PDF" variant="secondary" @click="downloadPDF" />
            </div>
          </aside>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.result-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.result-card {
  border: 1px solid var(--app-border);
  border-radius: 20px;
  box-shadow: var(--app-shadow-sm);
  background: var(--app-surface);
}

.result-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 24px;
}

.result-title {
  font-size: 1.8rem;
  font-weight: 700;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  color: var(--app-text-muted);
  font-size: 14px;
}

.result-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 20px;
  align-items: start;
}

.result-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.player-block,
.editor-block,
.export-panel {
  border: 1px solid var(--app-border);
  border-radius: 16px;
  background: var(--app-surface-soft);
  padding: 18px;
}

.block-title,
.export-title {
  margin-bottom: 14px;
  font-size: 1rem;
  font-weight: 700;
}

.audio-player {
  width: 100%;
}

.audio-empty {
  border: 1px dashed var(--app-border-strong);
  border-radius: 12px;
  background: #ffffff;
  color: var(--app-text-muted);
  padding: 18px;
  font-size: 14px;
}

.editor-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tool-button {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--app-border-strong);
  border-radius: 10px;
  background: #ffffff;
  color: var(--app-text);
  font-size: 14px;
  cursor: pointer;
}

.tool-button:hover {
  background: #eef2ff;
  border-color: var(--app-primary);
}

.editor-area {
  min-height: 420px;
  max-height: 520px;
  overflow-y: auto;
  border-radius: 14px;
  border: 1px solid var(--app-border-strong);
  background: #ffffff;
  color: var(--app-text);
  padding: 18px 20px;
  font-size: 16px;
  line-height: 1.65;
  outline: none;
  white-space: pre-wrap;
}

.editor-area:focus {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}

.export-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:deep(.p-card) {
  border-radius: 20px;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

:deep(.p-card-body) {
  padding: 24px;
}

@media print {
  .site-header,
  .player-block,
  .export-panel,
  .editor-toolbar {
    display: none !important;
  }

  .result-layout {
    display: block;
  }

  .editor-block {
    border: none;
    background: #ffffff;
    padding: 0;
  }

  .editor-area {
    border: none;
    max-height: none;
    overflow: visible;
  }
}

@media (max-width: 960px) {
  .result-layout {
    grid-template-columns: 1fr;
  }

  .editor-header {
    flex-direction: column;
  }

  .export-buttons {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
