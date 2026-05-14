<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import { getResult } from '../services/transcription.service'
import {
  getActiveTranscriptions,
  getTranscriptions,
  updateTranscription,
} from '../services/transcription-storage.service'

const router = useRouter()

const historyItems = ref([])
const pollingTimers = ref([])

const activeProcess = computed(() => {
  return historyItems.value.find((item) => {
    return item.status === 'Обробка' || item.status === 'Завантаження'
  })
})

const loadHistory = () => {
  historyItems.value = getTranscriptions()
}

const statusSeverity = (status) => {
  switch (status) {
    case 'Виконано':
      return 'success'
    case 'Обробка':
    case 'Завантаження':
      return 'warn'
    case 'Помилка':
      return 'danger'
    default:
      return 'secondary'
  }
}

const statusPercent = (status) => {
  switch (status) {
    case 'Завантаження':
      return 10
    case 'Обробка':
      return 60
    case 'Виконано':
      return 100
    case 'Помилка':
      return 0
    default:
      return 0
  }
}

const refreshActiveJob = async (item) => {
  if (!item.jobId) {
    return
  }

  try {
    const response = await getResult(item.jobId)

    if (response.status === 'not_ready') {
      updateTranscription(item.id, {
        status: 'Обробка',
        percent: 60,
        error: null,
      })

      loadHistory()
      return
    }

    if (response.status === 'success') {
      updateTranscription(item.id, {
        status: 'Виконано',
        percent: 100,
        result: response.result,
        audioUrl: response.audioUrl,
        error: null,
      })

      loadHistory()
      stopPolling()

      router.push({
        name: 'result',
        query: {
          id: item.id,
        },
      })

      return
    }

    updateTranscription(item.id, {
      status: 'Обробка',
      percent: 60,
      error: null,
    })

    loadHistory()
  } catch (error) {
    updateTranscription(item.id, {
      status: 'Помилка',
      percent: 0,
      error: error.message || 'Не вдалося отримати результат обробки.',
    })

    loadHistory()
  }
}

const startPolling = () => {
  stopPolling()

  const activeItems = getActiveTranscriptions()

  activeItems.forEach((item) => {
    refreshActiveJob(item)

    const timer = setInterval(() => {
      refreshActiveJob(item)
    }, 15000)

    pollingTimers.value.push(timer)
  })
}

const stopPolling = () => {
  pollingTimers.value.forEach((timer) => clearInterval(timer))
  pollingTimers.value = []
}

const goToResult = (event) => {
  const item = event.data

  if (item.status !== 'Виконано') {
    return
  }

  router.push({
    name: 'result',
    query: {
      id: item.id,
    },
  })
}

onMounted(() => {
  loadHistory()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="container history-view">
    <section class="page-head">
      <h1 class="section-title">Історія</h1>
      <p class="section-subtitle">
        Переглядай поточну обробку та відкривай готові результати транскрибації.
      </p>
    </section>

    <Card class="panel-card">
      <template #title>Процес обробки</template>

      <template #content>
        <div v-if="activeProcess" class="process-box">
          <div class="process-main">
            <div>
              <div class="process-name">{{ activeProcess.fileName }}</div>
              <div class="process-subtitle">Статус: {{ activeProcess.status }}</div>

              <div v-if="activeProcess.jobId" class="process-job">
                Job ID: {{ activeProcess.jobId }}
              </div>
            </div>

            <ProgressBar :value="activeProcess.percent || statusPercent(activeProcess.status)" />
          </div>
        </div>

        <div v-else class="empty-state">
          <div class="empty-title">Активної обробки немає</div>
          <p class="empty-text">Після завантаження файлу тут буде показано статус транскрибації.</p>
        </div>
      </template>
    </Card>

    <Card class="panel-card">
      <template #title>Історія завантажень</template>

      <template #content>
        <DataTable
          v-if="historyItems.length"
          :value="historyItems"
          stripedRows
          responsiveLayout="scroll"
          selectionMode="single"
          @row-click="goToResult"
        >
          <Column field="fileName" header="Назва файлу" />
          <Column field="date" header="Дата" />

          <Column header="Статус">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="statusSeverity(data.status)" />
            </template>
          </Column>

          <Column field="percent" header="%">
            <template #body="{ data }">
              {{ data.percent || statusPercent(data.status) }}%
            </template>
          </Column>
        </DataTable>

        <div v-else class="empty-state">
          <div class="empty-title">Історія поки порожня</div>
          <p class="empty-text">Завантажені файли з’являться тут після запуску транскрибації.</p>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.panel-card {
  border: 1px solid var(--app-border);
  border-radius: 20px;
  box-shadow: var(--app-shadow-sm);
  background: var(--app-surface);
}

.process-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.process-main {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.process-name {
  font-weight: 700;
  font-size: 1rem;
}

.process-subtitle {
  color: var(--app-text-muted);
  font-size: 14px;
}

.process-job {
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
  word-break: break-all;
}

.empty-state {
  border: 1px dashed var(--app-border-strong);
  border-radius: 16px;
  background: var(--app-surface-soft);
  padding: 28px;
  text-align: center;
}

.empty-title {
  margin-bottom: 6px;
  font-size: 1rem;
  font-weight: 700;
}

.empty-text {
  color: var(--app-text-muted);
  font-size: 14px;
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

:deep(.p-card-title) {
  font-size: 1.25rem;
  font-weight: 700;
}

:deep(.p-datatable) {
  background: var(--app-surface);
  color: var(--app-text);
}

:deep(.p-datatable-table-container) {
  border: 1px solid var(--app-border);
  border-radius: 14px;
  overflow: hidden;
}

:deep(.p-datatable-thead > tr > th) {
  background: var(--app-surface-soft);
  color: var(--app-text);
  border-bottom: 1px solid var(--app-border);
  font-weight: 600;
  font-size: 14px;
}

:deep(.p-datatable-tbody > tr > td) {
  border-bottom: 1px solid var(--app-border);
  color: var(--app-text);
  background: var(--app-surface);
}

:deep(.p-datatable-tbody > tr:last-child > td) {
  border-bottom: none;
}

:deep(.p-datatable-tbody > tr) {
  cursor: pointer;
  transition: background 0.2s ease;
}

:deep(.p-datatable-tbody > tr:hover) {
  background: #f8faff;
}

:deep(.p-progressbar) {
  height: 8px;
  border-radius: 999px;
  background: #eceff3;
}

:deep(.p-progressbar-value) {
  background: var(--app-primary);
}
</style>
