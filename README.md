# 🎙️ Xenlo - AI Transcription & Diarization Service

**Xenlo** — це інтелектуальний вебсервіс для автоматичної транскрибації аудіофайлів та діаризації (розділення розмови за спікерами) з використанням передових моделей машинного навчання.

## 🏗️ Архітектура проєкту (Monorepo)
Проєкт побудовано за принципом клієнт-серверної архітектури та розділено на два основні модулі в межах єдиного монорепозиторію:

* 📁 **`back-end/`** — Серверна частина. Побудована на **FastAPI** (Python). Відповідає за маршрутизацію запитів, взаємодію з Google Cloud Storage, Vertex AI та виконання ML-конвеєра (Whisper + Pyannote).
* 📁 **`front-end/`** — Клієнтська частина. Single Page Application (SPA), розроблене на **Vue.js**. Забезпечує зручний інтерфейс для завантаження медіафайлів, моніторингу статусу обробки та візуалізації результатів.

## 🚀 Технологічний стек
* **ML Models:** OpenAI Whisper (Medium), Pyannote Audio 3.1
* **Backend:** Python 3.10, FastAPI, Uvicorn, Docker
* **Frontend:** Vue.js, JavaScript, CSS
* **Cloud Infrastructure:** Google Cloud Run, Vertex AI Batch Prediction, Cloud Storage

## 👥 Команда розробки
* **Backend / DevOps / ML Engineering:** Maksym Svystun (@Ferichi)
* **Frontend / UI/UX Design:** Anna Klak (@klak-ann)
