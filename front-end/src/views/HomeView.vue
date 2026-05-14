<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import Select from 'primevue/select'
import AppButton from '../components/ui/AppButton.vue'
import AppUpload from '../components/ui/AppUpload.vue'
import { uploadAndStartTranscription } from '../services/transcription.service'
import { createTranscription, updateTranscription } from '../services/transcription-storage.service'

const router = useRouter()

const selectedLanguage = ref(null)
const selectedFile = ref(null)
const isProcessing = ref(false)
const errorMessage = ref('')
const statusMessage = ref('')

const languageOptions = [
  { label: 'Українська', value: 'uk' },
  { label: 'Англійська', value: 'en' },
]

const steps = [
  {
    number: '1.',
    title: 'Завантаження',
    text: 'Перетягніть аудіо- або відеофайл, або вставте посилання.',
  },
  {
    number: '2.',
    title: 'Обробка',
    text: 'Сервіс аналізує аудіо, розпізнає мову та ідентифікує дикторів.',
  },
  {
    number: '3.',
    title: 'Результат',
    text: 'Отримайте текст з розміткою дикторів та завантажте у потрібному форматі.',
  },
]

const features = [
  'Підтримувані файли для транскрибації: MP3, WAV, MP4, OGG, MOV',
  'Можливість обробки українською та англійською мовами',
  'Експорт результатів у зручному форматі: PDF, TXT, JSON',
]

const handleTranscribe = async () => {
  errorMessage.value = ''
  statusMessage.value = ''

  if (!selectedFile.value) {
    errorMessage.value = 'Будь ласка, оберіть файл для транскрибації.'
    return
  }

  if (!selectedLanguage.value) {
    errorMessage.value = 'Будь ласка, оберіть мову файлу.'
    return
  }

  const savedItem = createTranscription({
    fileName: selectedFile.value.name,
    language: selectedLanguage.value,
  })

  const handleTranscribe = async () => {
    errorMessage.value = ''

    if (!selectedFile.value) {
      errorMessage.value = 'Будь ласка, оберіть файл для транскрибації.'
      return
    }

    if (!selectedLanguage.value) {
      errorMessage.value = 'Будь ласка, оберіть мову файлу.'
      return
    }

    const savedItem = createTranscription({
      fileName: selectedFile.value.name,
      language: selectedLanguage.value,
      status: 'Завантаження',
      percent: 10,
    })

    // ОДРАЗУ переходимо на history
    router.push({
      name: 'history',
    })

    try {
      const response = await uploadAndStartTranscription({
        file: selectedFile.value,
        language: selectedLanguage.value,
      })

      updateTranscription(savedItem.id, {
        jobId: response.jobId,
        gcsPath: response.gcsPath,
        status: 'Обробка',
        percent: 50,
        error: null,
      })
    } catch (error) {
      updateTranscription(savedItem.id, {
        status: 'Помилка',
        percent: 0,
        error: error.message,
      })
    }
  }
}
</script>

<template>
  <div class="container home-view">
    <section class="upload-section">
      <Card class="upload-card">
        <template #content>
          <div class="upload-layout">
            <Select
              v-model="selectedLanguage"
              :options="languageOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Оберіть мову"
              class="full-width"
              :disabled="isProcessing"
            />

            <AppUpload v-model:file="selectedFile" />

            <div v-if="statusMessage" class="status-message">
              {{ statusMessage }}
            </div>

            <div v-if="errorMessage" class="error-message">
              {{ errorMessage }}
            </div>

            <div class="submit-row">
              <AppButton
                :label="isProcessing ? 'Обробка...' : 'Транскрибувати'"
                :disabled="isProcessing"
                @click="handleTranscribe"
              />
            </div>
          </div>
        </template>
      </Card>
    </section>

    <section class="content-section">
      <h2 class="simple-title">Як це працює ?</h2>

      <div class="steps-grid">
        <Card v-for="step in steps" :key="step.number" class="step-card">
          <template #content>
            <div class="step-card-inner">
              <div class="step-number">{{ step.number }}</div>
              <div>
                <h3 class="step-title">{{ step.title }}</h3>
                <p class="step-text">{{ step.text }}</p>
              </div>
            </div>
          </template>
        </Card>
      </div>
    </section>

    <section class="content-section">
      <h2 class="simple-title">Можливості</h2>

      <div class="features-grid">
        <Card v-for="feature in features" :key="feature" class="feature-card">
          <template #content>
            <div class="feature-card-inner">
              <span class="feature-icon">
                <i class="pi pi-check"></i>
              </span>
              <p>{{ feature }}</p>
            </div>
          </template>
        </Card>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  gap: 72px;
}

.upload-section {
  display: flex;
  justify-content: center;
}

.upload-card {
  width: min(100%, 720px);
}

.upload-layout {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.full-width {
  width: 100%;
}

.status-message {
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 500;
}

.error-message {
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fef2f2;
  color: #b91c1c;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 500;
}

.submit-row {
  display: flex;
  justify-content: center;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.simple-title {
  text-align: center;
  font-size: 2rem;
  font-weight: 700;
}

.steps-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.step-card,
.feature-card {
  height: 100%;
}

.step-card-inner {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.step-number {
  width: 42px;
  height: 42px;
  border-radius: 999px;
  background: #eef2ff;
  color: var(--app-primary);
  display: grid;
  place-items: center;
  font-weight: 800;
  flex-shrink: 0;
}

.step-title {
  margin-bottom: 8px;
  font-size: 1.1rem;
  font-weight: 700;
}

.step-text {
  color: var(--app-text-muted);
  font-size: 15px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

.feature-card-inner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  color: var(--app-text);
  font-size: 15px;
}

.feature-icon {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: #eef2ff;
  color: var(--app-primary);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

:deep(.p-card) {
  border-radius: 22px;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-sm);
}

:deep(.upload-card.p-card) {
  box-shadow: var(--app-shadow-md);
}

:deep(.p-card-body) {
  padding: 24px;
}

:deep(.p-select) {
  width: 100%;
}

@media (max-width: 960px) {
  .steps-grid,
  .features-grid {
    grid-template-columns: 1fr;
  }
}
</style>
