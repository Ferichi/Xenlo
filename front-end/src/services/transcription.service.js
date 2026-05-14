const BACKEND_URL = import.meta.env.VITE_BACKEND_URL

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const requestJson = async (url, options = {}) => {
  const response = await fetch(url, options)
  const text = await response.text()

  const parsedData = (() => {
    try {
      return text ? JSON.parse(text) : null
    } catch {
      return text
    }
  })()

  if (!response.ok) {
    const message =
      parsedData?.detail || parsedData?.message || parsedData?.error || 'Помилка запиту до сервера'

    const error = new Error(message)
    error.status = response.status
    error.data = parsedData
    throw error
  }

  return parsedData
}

export const checkBackendHealth = async () => {
  return requestJson(`${BACKEND_URL}/health`)
}

export const getUploadUrl = async (fileName) => {
  const encodedFileName = encodeURIComponent(fileName)

  // Основний варіант, який ми вже використовували раніше
  try {
    const result = await requestJson(`${BACKEND_URL}/get-upload-url?filename=${encodedFileName}`, {
      method: 'POST',
    })

    return result.data
  } catch {
    // Запасний варіант, якщо бек назвав ендпоінт інакше
    const result = await requestJson(`${BACKEND_URL}/getUploadUrl?filename=${encodedFileName}`, {
      method: 'GET',
    })

    return result.data
  }
}

export const uploadFileToStorage = async (uploadUrl, file) => {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': 'application/octet-stream',
    },
  })

  if (!response.ok) {
    throw new Error('Не вдалося завантажити файл у Google Cloud Storage')
  }
}

export const startTranscription = async ({ gcsPath, language }) => {
  const result = await requestJson(`${BACKEND_URL}/predict`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      gcs_path: gcsPath,
      language,
    }),
  })

  return result
}

export const getResult = async (jobId) => {
  try {
    const result = await requestJson(`${BACKEND_URL}/getResult/${jobId}`)

    const item = result.data?.[0]

    return {
      status: result.status,
      data: item,
      result: item?.result || null,
      audioUrl: item?.audio_player_url || '',
    }
  } catch (error) {
    if (error.status === 400 && error.data?.status === 'not_ready') {
      return {
        status: 'not_ready',
        detail: error.data.detail,
      }
    }

    throw error
  }
}

export const waitForResult = async (jobId, onStatusChange) => {
  while (true) {
    await delay(15000)

    const response = await getResult(jobId)

    if (response.status === 'success') {
      return response
    }

    if (response.status === 'not_ready') {
      if (onStatusChange) {
        onStatusChange(response.detail || 'Файл ще обробляється...')
      }

      continue
    }

    throw new Error('Невідомий статус обробки')
  }
}

export const uploadAndStartTranscription = async ({ file, language }) => {
  const { upload_url, gcs_path } = await getUploadUrl(file.name)

  await uploadFileToStorage(upload_url, file)

  const response = await startTranscription({
    gcsPath: gcs_path,
    language,
  })

  return {
    fileName: file.name,
    gcsPath: gcs_path,
    jobId: response.job_id,
    status: response.status,
    message: response.message,
  }
}
