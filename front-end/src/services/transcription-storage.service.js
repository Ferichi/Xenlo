const STORAGE_KEY = 'xenlo_transcriptions'

export const getTranscriptions = () => {
  const saved = localStorage.getItem(STORAGE_KEY)

  if (!saved) {
    return []
  }

  try {
    return JSON.parse(saved)
  } catch {
    return []
  }
}

export const saveTranscriptions = (items) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export const createTranscription = ({ fileName, language }) => {
  const item = {
    id: crypto.randomUUID(),
    jobId: null,
    fileName,
    language,
    status: 'Завантаження',
    percent: 10,
    date: new Date().toLocaleString('uk-UA'),
    result: null,
    error: null,
  }

  const items = getTranscriptions()
  saveTranscriptions([item, ...items])

  return item
}

export const updateTranscription = (id, patch) => {
  const items = getTranscriptions()

  const updatedItems = items.map((item) => {
    if (item.id !== id) {
      return item
    }

    return {
      ...item,
      ...patch,
    }
  })

  saveTranscriptions(updatedItems)

  return updatedItems.find((item) => item.id === id)
}

export const getTranscriptionById = (id) => {
  return getTranscriptions().find((item) => item.id === id)
}

export const getActiveTranscriptions = () => {
  return getTranscriptions().filter((item) => {
    return item.jobId && item.status === 'Обробка'
  })
}
