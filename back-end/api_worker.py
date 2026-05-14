import os
import gc
import uuid
import json
import warnings
import time
import datetime
from contextlib import asynccontextmanager
from typing import Optional
import datetime
import torch
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pyannote.audio import Pipeline
from google.cloud import storage
from google.cloud import aiplatform
from google.auth.transport import requests as google_requests
import google.auth
import whisper
import librosa
import uvicorn
import json
import traceback
from fastapi.concurrency import run_in_threadpool
# --- ПАТЧ СУМІСНОСТІ NUMPY 2.0 ---
import numpy as np

if not hasattr(np, "NaN"):
    np.NaN = np.nan
if not hasattr(np, "float"):
    np.float = float
warnings.filterwarnings("ignore")

device = "cuda" if torch.cuda.is_available() else "cpu"
models = {"whisper": None, "pyannote": None}

# ──────────────────────────────────────────────
# ENV ЗМІННІ
# ──────────────────────────────────────────────

GCP_PROJECT_ID          = os.getenv("GCP_PROJECT_ID", "audiotest-493510")
GCP_LOCATION            = os.getenv("GCP_LOCATION", "europe-west3")
VERTEX_MODEL_RESOURCE_NAME = os.getenv("VERTEX_MODEL_RESOURCE_NAME", "")
GCS_BUCKET_NAME         = os.getenv("GCS_BUCKET_NAME", "bucket_audiov1")
GCS_INPUT_LIST_PREFIX   = os.getenv("GCS_INPUT_LIST_PREFIX", "gs://bucket_audiov1/batch_inputs/")
GCS_OUTPUT_PREFIX       = os.getenv("GCS_OUTPUT_PREFIX", "gs://bucket_audiov1/batch_results/")
# Сервіс-акаунт для Vertex AI Batch Job (щоб не брав дефолтний без потрібних прав)
VERTEX_SERVICE_ACCOUNT  = os.getenv("VERTEX_SERVICE_ACCOUNT", "")
IS_VERTEX_WORKER = os.getenv("IS_VERTEX_WORKER", "false").lower() == "true"

# Поріг тривалості для вибору між онлайн та batch обробкою (секунди)
BATCH_THRESHOLD_SECONDS = float(os.getenv("BATCH_THRESHOLD_SECONDS", "180"))

# ──────────────────────────────────────────────
# ЛОГУВАННЯ
# ──────────────────────────────────────────────

def log(icon: str, message: str):
    print(f"{icon} {message}", flush=True)

# ──────────────────────────────────────────────
# ЗАВАНТАЖЕННЯ МОДЕЛЕЙ (один раз при старті)
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log("🚀", f"Ініціалізація AI-сервісу | Пристрій: {device.upper()} | Vertex Worker: {IS_VERTEX_WORKER}")

    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        log("🔑", "HF_TOKEN знайдено — використовується персональний ключ.")
    else:
        log("⚠️", "HF_TOKEN не знайдено! Pyannote може не завантажитись.")

    # FIX: Ініціалізуємо aiplatform один раз при старті — не в кожному запиті
    if GCP_PROJECT_ID:
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        log("☁️", f"Vertex AI ініціалізовано: project={GCP_PROJECT_ID}, location={GCP_LOCATION}")
    else:
        log("⚠️", "GCP_PROJECT_ID не встановлено — Vertex AI недоступний.")

    try:
        log("🗣️", "КРОК 1/2: Завантаження Pyannote (діаризація)...")
        try:
            models["pyannote"] = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token,
            )
        except TypeError:
            log("🔄", "Стара версія Pipeline — fallback до use_auth_token...")
            models["pyannote"] = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            )

        if device == "cuda":
            models["pyannote"].to(torch.device("cuda"))
        log("✅", "Pyannote готовий!")

        log("📦", "КРОК 2/2: Завантаження Whisper Medium...")
        models["whisper"] = whisper.load_model("medium", device=device)
        log("✅", "Whisper готовий!")

        log("🟢", "СЕРВЕР ГОТОВИЙ. Endpoints: /predict | /batchPredict | /batchStatus/{id} | /getResult/{id} | /get-upload-url")
        yield

    except Exception as e:
        log("💥", f"КРИТИЧНА ПОМИЛКА ПРИ СТАРТІ: {e}")
        raise
    finally:
        log("🛑", "Зупинка сервера — очищення пам'яті...")
        models.clear()
        if device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()


app = FastAPI(title="AI Transcription Service v2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# ДОПОМІЖНІ ФУНКЦІЇ — CLOUD STORAGE ТА АУДІО
# ──────────────────────────────────────────────

def download_from_gcs(gcs_path: str) -> str:
    """Завантажує файл із GCS у /tmp із унікальним іменем."""
    log("☁️", f"Завантаження з GCS: {gcs_path}")
    try:
        parts = gcs_path.replace("gs://", "").split("/", 1)
        # FIX: strip() щоб прибрати зайві слеші якщо є
        bucket_name = parts[0].strip("/")
        blob_name = parts[1].strip("/")
        log("🪣", f"Бакет: '{bucket_name}' | Blob: '{blob_name}'")
        # FIX: явно вказуємо project щоб клієнт не шукав його "всліпу"
        client = storage.Client(project=GCP_PROJECT_ID)
        blob = client.bucket(bucket_name).blob(blob_name)
        local_path = f"/tmp/{uuid.uuid4()}_{blob_name.split('/')[-1]}"
        blob.download_to_filename(local_path)
        log("✅", f"GCS файл збережено: {local_path}")
        return local_path
    except Exception as e:
        log("❌", f"Помилка завантаження з GCS: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download from GCS: {e}")


def get_audio_duration(local_path: str) -> float:
    """Визначає тривалість аудіо в секундах."""
    try:
        duration = librosa.get_duration(path=local_path)
        log("🕒", f"Тривалість файлу: {duration:.2f} сек.")
        return duration
    except Exception as e:
        log("⚠️", f"Не вдалося визначити тривалість: {e}")
        return 0.0

# ──────────────────────────────────────────────
# ДОПОМІЖНІ ФУНКЦІЇ — VERTEX AI BATCH
# ──────────────────────────────────────────────

def create_batch_prediction_job(
        gcs_source_uri: str,
        language: str,
        num_speakers: Optional[int] = None,
        job_display_name: Optional[str] = None,
) -> dict:
    """Створює Batch Prediction Job у Vertex AI."""

    # FIX: Перевірка що модель налаштована перед створенням job
    if not VERTEX_MODEL_RESOURCE_NAME:
        raise ValueError(
            "VERTEX_MODEL_RESOURCE_NAME не встановлено! "
            "Додай змінну середовища з повним resource name моделі."
        )

    job_id_short = str(uuid.uuid4())[:8]
    display_name = job_display_name or f"transcription_batch_{job_id_short}"

    # FIX: Формат JSONL — кастомна модель очікує словник, не plain URI
    instance_dict = {"gcs_path": gcs_source_uri, "language": language}
    if num_speakers:
        instance_dict["num_speakers"] = num_speakers

    file_list_content = json.dumps(instance_dict) + "\n"
    file_list_filename = f"input_list_{job_id_short}.jsonl"

    try:
        # FIX: явно вказуємо project щоб клієнт не шукав його "всліпу"
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"batch_inputs/{file_list_filename}")
        blob.upload_from_string(file_list_content, content_type="application/json")

        file_list_gcs_uri = f"gs://{GCS_BUCKET_NAME}/batch_inputs/{file_list_filename}"
        log("📝", f"Створено JSONL інстанс: {file_list_gcs_uri}")
        log("🚀", f"Запуск Batch Prediction | Джерело: {gcs_source_uri}")

        # FIX: aiplatform.init() вже викликано в lifespan — тут не потрібен
        create_kwargs = dict(
            job_display_name=display_name,
            model_name=VERTEX_MODEL_RESOURCE_NAME,
            instances_format="jsonl",
            predictions_format="jsonl",
            gcs_source=[file_list_gcs_uri],
            gcs_destination_prefix=GCS_OUTPUT_PREFIX,
            machine_type="n1-standard-8",
            sync=False,
        )
        # FIX: явно вказуємо service_account щоб Vertex не брав дефолтний без прав на GCS
        if VERTEX_SERVICE_ACCOUNT:
            create_kwargs["service_account"] = VERTEX_SERVICE_ACCOUNT
            log("🔐", f"Використовується сервіс-акаунт: {VERTEX_SERVICE_ACCOUNT}")
        else:
            log("⚠️", "VERTEX_SERVICE_ACCOUNT не встановлено — використовується дефолтний акаунт.")

        batch_job = aiplatform.BatchPredictionJob.create(**create_kwargs)

        # FIX: try/except навколо resource_name — він кидає RuntimeError якщо не готовий
        log("⏳", "Очікування ініціалізації BatchPredictionJob...")
        resource_name = None
        for i in range(15):  # 45 секунд максимум
            try:
                resource_name = batch_job.resource_name
                if resource_name:
                    log("✅", f"Ресурс готовий на спробі {i + 1}: {resource_name}")
                    break
            except RuntimeError:
                pass
            log("💤", f"Спроба {i + 1}/15: ресурс ще не готовий...")
            time.sleep(3.0)

        if not resource_name:
            raise Exception(
                "Vertex AI не створив ресурс за 45 секунд. "
                "Перевір VERTEX_MODEL_RESOURCE_NAME та права сервіс-акаунту на Vertex AI."
            )

        # Витягуємо числовий job_id з resource_name для зручності фронтенду
        job_numeric_id = resource_name.split("/")[-1]

        log("✅", f"Batch Job успішно створено: {resource_name}")

        return {
            "job_id": job_numeric_id,
            "job_resource_name": resource_name,
            "job_display_name": display_name,
            "state": batch_job.state.name,
            "output_prefix": GCS_OUTPUT_PREFIX,
        }

    except Exception as e:
        log("❌", f"Помилка створення Batch Job: {str(e)}")
        log("🔍", f"Деталі: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Vertex AI error: {str(e)}")

# ──────────────────────────────────────────────
# PIPELINE — ОНЛАЙН ОБРОБКА
# ──────────────────────────────────────────────

def extract_speaker_segments(diarization) -> list[tuple]:
    """Витягує (start, end, speaker) з об'єкту pyannote."""

    def _from_annotation(obj):
        if hasattr(obj, "itertracks"):
            return [(t.start, t.end, spk) for t, _, spk in obj.itertracks(yield_label=True)]
        return None

    segments = _from_annotation(diarization)
    if segments is not None:
        return segments

    log("🔎", f"Нестандартний тип {type(diarization).__name__} — глибоке сканування...")
    for attr in dir(diarization):
        if attr.startswith("_"):
            continue
        try:
            inner = getattr(diarization, attr)
            result = _from_annotation(inner)
            if result is not None:
                log("✅", f"Знайдено сегменти в атрибуті '{attr}'")
                return result
        except Exception:
            continue

    log("❌", f"Не вдалося розпакувати об'єкт. Атрибути: {dir(diarization)}")
    return []

def merge_whisper_and_diarization(whisper_segments: list, speaker_segments: list) -> list[dict]:
    """Для кожного Whisper-сегменту знаходить спікера з найбільшим перекриттям."""
    results = []
    for seg in whisper_segments:
        w_start, w_end = seg["start"], seg["end"]
        text = seg["text"].strip()
        best_speaker = "SPEAKER_UNKNOWN"
        max_overlap = 0.0
        for d_start, d_end, speaker in speaker_segments:
            overlap = max(0.0, min(w_end, d_end) - max(w_start, d_start))
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = speaker
        results.append({
            "start": round(w_start, 2),
            "end": round(w_end, 2),
            "speaker": best_speaker,
            "text": text,
        })
    return results

def generate_signed_url(bucket_name: str, blob_name: str) -> str:
    """
    Створює тимчасове посилання (на 1 годину) для доступу до файлу в приватному бакеті GCS.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Генеруємо посилання, яке дозволяє лише читання (GET)
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=1),
        method="GET",
    )
    return url

def find_vertex_result_file(bucket_name: str, base_prefix: str) -> str:
    """
    Шукає файл із результатами транскрибації всередині динамічних папок Vertex AI.
    base_prefix - це папка, куди ти вказав зберігати результати (наприклад, 'batch_results/')
    """
    client = storage.Client()

    # Отримуємо всі файли, що лежать у вказаній директорії
    blobs = client.list_blobs(bucket_name, prefix=base_prefix)

    # Шукаємо той самий файл результату
    for blob in blobs:
        if "prediction.results" in blob.name:
            return blob.name  # Повертає повний шлях, наприклад: batch_results/prediction-123/prediction.results-00000-of-00001

    return None

def get_final_response_for_frontend(bucket_name: str, audio_blob_name: str, vertex_output_prefix: str):
    """
    Формує фінальну відповідь для клієнтської частини.
    audio_blob_name - шлях до оригінального аудіо (наприклад, 'uploads/audio.mp4')
    vertex_output_prefix - папка результатів (наприклад, 'batch_results/')
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # 1. Шукаємо файл результату Vertex AI
    result_blob_name = find_vertex_result_file(bucket_name, vertex_output_prefix)
    if not result_blob_name:
        return {"error": "Результат ще не готовий або файл не знайдено"}

    # 2. Читаємо знайдений JSON-файл прямо з пам'яті (без збереження на диск)
    result_blob = bucket.blob(result_blob_name)
    result_content = result_blob.download_as_text()

    # Vertex AI повертає JSON Lines, тому парсимо перший рядок
    transcription_data = json.loads(result_content.strip().split('\n')[0])

    # 3. Генеруємо Signed URL для вебплеєра Ані
    audio_player_url = generate_signed_url(bucket_name, audio_blob_name)

    # 4. Формуємо красиву відповідь
    return {
        "status": "completed",
        "audio_player_url": audio_player_url,
        "transcription": transcription_data.get("prediction", {})
    }

def _run_pipeline(
        tmp_path: str,
        language: str,
        num_speakers: Optional[int],
) -> dict:
    """Повний онлайн-pipeline: діаризація → транскрипція → злиття. Повертає dict."""
    start_time = time.time()

    log("🎵", "Декодування аудіо (librosa, 16kHz)...")
    waveform, sr = librosa.load(tmp_path, sr=16000, mono=True)
    audio_tensor = torch.from_numpy(waveform).float().unsqueeze(0)
    if device == "cuda":
        audio_tensor = audio_tensor.to(device)
    log("✅", f"Аудіо: {waveform.shape[0] / sr:.1f}с, {sr}Hz")

    log("👥", "Аналіз спікерів (Pyannote)...")
    if num_speakers:
        log("🔢", f"Очікувана кількість спікерів: {num_speakers}")

    try:
        diarization = models["pyannote"](
            tmp_path,
            **{"num_speakers": num_speakers} if num_speakers else {}
        )
    except Exception as e:
        log("⚠️", f"Читання по шляху не вдалось ({e}), використовую тензор...")
        kwargs = {"waveform": audio_tensor, "sample_rate": sr}
        if num_speakers:
            kwargs["num_speakers"] = num_speakers
        diarization = models["pyannote"](kwargs)

    speaker_segments = extract_speaker_segments(diarization)
    unique_speakers = len(set(s[2] for s in speaker_segments))
    log("✅", f"Знайдено {len(speaker_segments)} фрагментів від {unique_speakers} спікерів.")

    log("📝", f"Транскрипція (Whisper, мова: '{language}')...")
    whisper_result = models["whisper"].transcribe(
        tmp_path,
        language=language,
        fp16=(device == "cuda"),
        verbose=False,
    )
    log("✅", f"Розпізнано {len(whisper_result['segments'])} сегментів.")

    log("🔗", "Злиття транскрипції та діаризації...")
    merged = merge_whisper_and_diarization(whisper_result["segments"], speaker_segments)
    overall_text = " ".join(seg["text"] for seg in merged)
    processing_time = round(time.time() - start_time, 2)
    log("🟢", f"Готово! Час обробки: {processing_time}с")

    # FIX: повертаємо dict, а не JSONResponse — щоб caller міг пакувати як хоче
    return {
        "overall_text": overall_text,
        "segments": merged,
        "processing_time": processing_time,
    }

# ──────────────────────────────────────────────
# ФОНОВА ОБРОБКА — BACKGROUND TASK
# ──────────────────────────────────────────────

def process_and_save_background(
    tmp_path: str,
    language: str,
    num_speakers: Optional[int],
    job_id: str,
    bucket_name: str,
    original_gcs_path: str,
):
    """
    Виконує важку обробку у фоні (після того, як фронтенд вже отримав job_id).
    Результат зберігається у GCS, щоб /getResult/{job_id} міг його знайти.
    """
    try:
        log("🏃", f"[БГ] Стартує фонова обробка для Job ID: {job_id}")

        # 1. Запускаємо важкий pipeline (синхронно — ми вже у фоновому потоці)
        result_data = _run_pipeline(tmp_path, language, num_speakers)

        # 2. Зберігаємо результат у GCS у форматі, сумісному з /getResult
        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(bucket_name)

        # Шлях відповідає структурі, яку очікує /getResult для batch_results
        blob = bucket.blob(f"batch_results/prediction-{job_id}/prediction.results-00000-of-00001")

        # Формуємо JSONL-рядок у форматі Vertex AI (instance + prediction)
        output_json = json.dumps({
            "instance": {
                "gcs_path": original_gcs_path,
                "language": language,
            },
            "prediction": result_data,
        }, ensure_ascii=False)

        blob.upload_from_string(output_json, content_type="application/json")
        log("✅", f"[БГ] Результат збережено у GCS для Job ID: {job_id}")

    except Exception as e:
        log("❌", f"[БГ] Помилка фонової обробки {job_id}: {e}")
        log("🔍", f"[БГ] Деталі: {traceback.format_exc()}")
    finally:
        # Завжди прибираємо тимчасовий файл після обробки
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            log("🗑️", f"[БГ] Тимчасовий файл видалено: {tmp_path}")
        if device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()

# ──────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────

@app.post("/predict")
async def predict(request: Request, background_tasks: BackgroundTasks):
    """
    Розумний роутер:
    - Читає JSON (від Vertex AI Batch) та Form-Data (від клієнтів).
    - Якщо IS_VERTEX_WORKER=true або запит від Vertex — синхронна онлайн обробка (без рекурсії).
    - Якщо файл > BATCH_THRESHOLD_SECONDS і запит від клієнта — створює Batch Job.
    - Якщо файл ≤ BATCH_THRESHOLD_SECONDS і запит від клієнта — миттєво повертає job_id,
      обробка йде у фоні через BackgroundTasks, результат зберігається у GCS.
    """
    file_bytes = None
    file_name = None
    gcs_path = None
    language = "uk"
    num_speakers = None

    content_type = request.headers.get("content-type", "")

    # FIX: Vertex AI надсилає JSON; визначаємо це надійно через env прапор або content-type
    is_vertex_request = IS_VERTEX_WORKER or "application/json" in content_type

    if is_vertex_request:
        # FIX: Vertex AI Batch шле інстанс НАПРЯМУ, не обгорнутий в {"instances": [...]}
        # Але для сумісності з онлайн-предикшеном підтримуємо обидва формати
        data = await request.json()
        if "instances" in data and isinstance(data["instances"], list) and data["instances"]:
            instance = data["instances"][0]
        else:
            instance = data  # Batch формат — інстанс напряму

        gcs_path = instance.get("gcs_path")
        language = instance.get("language", "uk")
        ns = instance.get("num_speakers")
        if ns:
            num_speakers = int(ns)

        log("🤖", f"Vertex AI запит | gcs_path={gcs_path} | мова={language}")
    else:
        form = await request.form()
        if "file" in form and hasattr(form["file"], "filename") and form["file"].filename:
            file_obj = form["file"]
            file_bytes = await file_obj.read()
            file_name = file_obj.filename
        gcs_path = form.get("gcs_path")
        language = form.get("language", "uk")
        ns = form.get("num_speakers")
        if ns:
            num_speakers = int(ns)

        log("👤", f"Клієнтський запит | файл={file_name} | gcs={gcs_path} | мова={language}")

    if not models["whisper"] or not models["pyannote"]:
        raise HTTPException(status_code=503, detail="AI моделі ще завантажуються.")

    if not file_bytes and not gcs_path:
        raise HTTPException(status_code=400, detail="Потрібен або 'file', або 'gcs_path'.")

    tmp_path = None
    try:
        # Отримуємо файл локально
        if gcs_path and str(gcs_path).startswith("gs://"):
            tmp_path = download_from_gcs(gcs_path)
        elif file_bytes:
            tmp_path = f"/tmp/{uuid.uuid4()}_{file_name or 'audio'}"
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
            log("💾", f"Збережено: {tmp_path}")
        else:
            raise HTTPException(status_code=400, detail="Некоректний gcs_path або файл.")

        duration = get_audio_duration(tmp_path)

        # ── VERTEX WORKER: завжди синхронна обробка (ніколи не у фоні) ──
        if is_vertex_request:
            log("🚀", "Vertex worker — синхронна онлайн обробка...")
            result_data = await run_in_threadpool(_run_pipeline, tmp_path, language, num_speakers)
            # tmp_path чиститься у finally нижче
            return JSONResponse(content={"predictions": [result_data]})

        # ── ДОВГИЙ ФАЙЛ від клієнта: Vertex AI Batch Job ──
        if duration >= BATCH_THRESHOLD_SECONDS:
            log("🏭", f"Довгий файл ({duration:.0f}с) від клієнта — створюємо Batch Job...")

            # Якщо файл прийшов через multipart — спочатку завантажуємо в GCS
            final_gcs_uri = gcs_path
            if not gcs_path:
                client = storage.Client(project=GCP_PROJECT_ID)
                blob_name = f"uploads/auto_{uuid.uuid4().hex[:8]}_{file_name}"
                blob = client.bucket(GCS_BUCKET_NAME).blob(blob_name)
                blob.upload_from_filename(tmp_path)
                final_gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
                log("☁️", f"Файл завантажено в GCS: {final_gcs_uri}")

            job_info = create_batch_prediction_job(
                gcs_source_uri=final_gcs_uri,
                language=language,
                num_speakers=num_speakers,
            )
            return JSONResponse(content={
                "status": "accepted_batch",
                "message": f"Файл {duration:.0f}с — запущено Batch Job. Перевіряй статус через /batchStatus/{{job_id}}",
                "data": job_info,
            })

        # ── КОРОТКИЙ ФАЙЛ від клієнта: фонова обробка через BackgroundTasks ──
        log("⚡", f"Короткий файл ({duration:.0f}с) — передаємо у фонову обробку...")

        job_id = str(uuid.uuid4())

        # Визначаємо original_gcs_path для збереження в результаті
        original_gcs_path = gcs_path or f"gs://{GCS_BUCKET_NAME}/uploads/{os.path.basename(tmp_path)}"

        # Якщо файл прийшов як upload (не з GCS) — завантажуємо в GCS,
        # щоб фонова функція мала доступ до нього навіть після завершення запиту
        if not gcs_path and file_bytes:
            client = storage.Client(project=GCP_PROJECT_ID)
            blob_name = f"uploads/{uuid.uuid4().hex[:8]}_{file_name or 'audio'}"
            blob = client.bucket(GCS_BUCKET_NAME).blob(blob_name)
            blob.upload_from_filename(tmp_path)
            original_gcs_path = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
            log("☁️", f"Файл завантажено в GCS для фонової обробки: {original_gcs_path}")

        # 🟢 Передаємо важку роботу у фон (БЕЗ await — не блокуємо відповідь)
        # tmp_path буде видалено всередині process_and_save_background у finally
        background_tasks.add_task(
            process_and_save_background,
            tmp_path=tmp_path,
            language=language,
            num_speakers=num_speakers,
            job_id=job_id,
            bucket_name=GCS_BUCKET_NAME,
            original_gcs_path=original_gcs_path,
        )

        # Скидаємо tmp_path щоб finally нижче не видалив файл передчасно
        tmp_path = None

        # 🟢 МИТТЄВА відповідь фронтенду (за мілісекунди)
        log("📤", f"Миттєва відповідь фронтенду. Job ID: {job_id}")
        return JSONResponse(content={
            "status": "processing",
            "job_id": job_id,
            "message": "Обробка розпочата у фоновому режимі. Перевіряй результат через /getResult/{job_id}",
        })

    except HTTPException:
        raise
    except Exception as e:
        log("❌", f"Помилка обробки: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Видаляємо tmp_path лише якщо він ще не переданий у фонову задачу
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if device == "cuda" and not background_tasks:
            torch.cuda.empty_cache()
            gc.collect()

# FIX: /rawPredict → просто аліас на /predict (уникаємо дублювання логіки)
@app.post("/rawPredict")
async def raw_predict(request: Request, background_tasks: BackgroundTasks):
    """Аліас /predict для сумісності."""
    return await predict(request, background_tasks)

@app.post("/batchPredict")
async def batch_predict(request: Request):
    """
    Явний endpoint для запуску Batch Job.
    Приймає Form-Data або JSON: { gcs_path, language, num_speakers?, job_display_name? }
    """
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        data = await request.json()
        gcs_path = data.get("gcs_path")
        language = data.get("language", "uk")
        num_speakers = data.get("num_speakers")
        job_display_name = data.get("job_display_name")
    else:
        form = await request.form()
        gcs_path = form.get("gcs_path")
        language = form.get("language", "uk")
        ns = form.get("num_speakers")
        num_speakers = int(ns) if ns else None
        job_display_name = form.get("job_display_name")

    if not gcs_path or not str(gcs_path).startswith("gs://"):
        raise HTTPException(
            status_code=400,
            detail="Потрібен gcs_path у форматі gs://bucket/file."
        )

    log("🏭", f"Запит на Batch Prediction | Файл: {gcs_path} | Мова: {language}")

    try:
        job_info = create_batch_prediction_job(
            gcs_source_uri=gcs_path,
            language=language,
            num_speakers=num_speakers,
            job_display_name=job_display_name,
        )
        return JSONResponse(content={"status": "accepted", "data": job_info})
    except HTTPException:
        raise
    except Exception as e:
        log("❌", f"Помилка запуску Batch Job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/batchStatus/{job_id}")
async def batch_status(job_id: str):
    """Перевірка стану Batch Job за числовим ID."""
    log("🔍", f"Перевірка стану Batch Job ID: {job_id}")
    try:
        resource_name = (
            f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}"
            f"/batchPredictionJobs/{job_id}"
        )
        job = aiplatform.BatchPredictionJob(resource_name)
        return JSONResponse(content={
            "status": "success",
            "data": {
                "job_id": job_id,
                "job_display_name": job.display_name,
                "state": job.state.name,
                "output_prefix": GCS_OUTPUT_PREFIX,
                "create_time": str(job.create_time),
            },
        })
    except Exception as e:
        log("❌", f"Помилка отримання стану Job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/getResult/{job_id}")
async def get_result(job_id: str):
    """
    Забирає готовий результат із бакета.
    Підтримує два режими:
    - Фонова (online) обробка: шукає файл batch_results/prediction-{job_id}/...
    - Vertex AI Batch Job: спочатку перевіряє стан job, потім читає output
    """
    log("📥", f"Запит на отримання результату для Job ID: {job_id}")

    # ── Спершу перевіряємо чи є вже готовий результат від фонової (online) обробки ──
    try:
        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(GCS_BUCKET_NAME)
        online_prefix = f"batch_results/prediction-{job_id}/"
        online_blobs = list(bucket.list_blobs(prefix=online_prefix))
        online_result_blob = next((b for b in online_blobs if "prediction.results" in b.name), None)

        if online_result_blob:
            log("✅", f"Знайдено результат онлайн-обробки: {online_result_blob.name}")
            content = online_result_blob.download_as_text()
            raw = json.loads(content.strip().split('\n')[0])

            instance = raw.get("instance", {})
            prediction = raw.get("prediction", raw)
            gcs_path = instance.get("gcs_path", "")

            audio_player_url = ""
            if gcs_path and gcs_path.startswith(f"gs://{GCS_BUCKET_NAME}/"):
                blob_name = gcs_path.replace(f"gs://{GCS_BUCKET_NAME}/", "")
                try:
                    audio_player_url = generate_signed_url(GCS_BUCKET_NAME, blob_name)
                except Exception as e:
                    log("⚠️", f"Не вдалося згенерувати Signed URL: {e}")

            return JSONResponse(content={
                "status": "success",
                "data": [{
                    "gcs_path": gcs_path,
                    "audio_player_url": audio_player_url,
                    "language": instance.get("language", ""),
                    "result": prediction,
                }],
            })

    except Exception as e:
        log("⚠️", f"Помилка пошуку онлайн-результату: {e}")

    # ── Якщо онлайн-результату нема — пробуємо як Vertex AI Batch Job ──
    try:
        resource_name = (
            f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}"
            f"/batchPredictionJobs/{job_id}"
        )
        job = aiplatform.BatchPredictionJob(resource_name)

        if job.state.name != "JOB_STATE_SUCCEEDED":
            return JSONResponse(
                status_code=400,
                content={
                    "status": "not_ready",
                    "detail": f"Завдання ще не завершено. Статус: {job.state.name}",
                }
            )

        gcs_output_dir = job.output_info.gcs_output_directory
        log("📂", f"Результат Vertex у GCS: {gcs_output_dir}")

        path_parts = gcs_output_dir.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        prefix = path_parts[1] if len(path_parts) > 1 else ""

        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        jsonl_blob = next((b for b in blobs if "prediction.results" in b.name), None)

        if not jsonl_blob:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "detail": "Файл із результатом не знайдено в бакеті."}
            )

        content = jsonl_blob.download_as_text()
        results = []
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            raw = json.loads(line)

            prediction = raw.get("prediction", raw)

            if isinstance(prediction, dict) and "predictions" in prediction:
                inner = prediction["predictions"]
                prediction = inner[0] if isinstance(inner, list) and inner else inner

            if isinstance(prediction, dict) and "data" in prediction and len(prediction) <= 2:
                prediction = prediction["data"]

            instance = raw.get("instance", {})
            gcs_path = instance.get("gcs_path", "")

            audio_player_url = ""
            if gcs_path and gcs_path.startswith(f"gs://{bucket_name}/"):
                blob_name = gcs_path.replace(f"gs://{bucket_name}/", "")
                try:
                    audio_player_url = generate_signed_url(bucket_name, blob_name)
                    log("🔗", f"Згенеровано Signed URL для плеєра: {blob_name}")
                except Exception as e:
                    log("⚠️", f"Не вдалося згенерувати Signed URL: {e}")

            results.append({
                "gcs_path": gcs_path,
                "audio_player_url": audio_player_url,
                "language": instance.get("language", ""),
                "result": prediction,
            })

        log("✅", f"Результат Vertex успішно зчитано ({len(results)} рядків).")
        return JSONResponse(content={"status": "success", "data": results})

    except Exception as e:
        log("❌", f"Помилка отримання результату: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/get-upload-url")
async def get_upload_url(filename: str):
    """
    Генерує тимчасовий Signed URL (v4, 15 хв) для прямого завантаження з браузера у GCS.
    Флоу: POST /get-upload-url?filename=meeting.mp3
          PUT upload_url (бінарний файл)
          POST /batchPredict { gcs_path, language }
    """
    log("🔗", f"Генерація Signed URL для файлу: {filename}")
    try:
        credentials, _ = google.auth.default()
        auth_request = google_requests.Request()
        credentials.refresh(auth_request)
        service_account_email = credentials.service_account_email

        if not service_account_email:
            raise ValueError("Не вдалося визначити Service Account Email")

        client = storage.Client(project=GCP_PROJECT_ID)
        blob_name = f"uploads/{uuid.uuid4()}_{filename}"
        blob = client.bucket(GCS_BUCKET_NAME).blob(blob_name)

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            service_account_email=service_account_email,
            access_token=credentials.token,
        )

        gcs_path = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
        log("✅", f"Signed URL згенеровано | GCS шлях: {gcs_path}")

        return JSONResponse(content={
            "status": "success",
            "data": {
                "upload_url": url,
                "gcs_path": gcs_path,
                "expires_in_minutes": 15,
            },
        })
    except Exception as e:
        log("❌", f"Помилка генерації Signed URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Healthcheck для Docker та Vertex AI."""
    whisper_ok = models["whisper"] is not None
    pyannote_ok = models["pyannote"] is not None
    return {
        "status": "ready" if (whisper_ok and pyannote_ok) else "loading",
        "device": device,
        "is_vertex_worker": IS_VERTEX_WORKER,
        "models": {
            "whisper": "loaded" if whisper_ok else "not_loaded",
            "pyannote": "loaded" if pyannote_ok else "not_loaded",
        },
        "vertex_ai": {
            "project": GCP_PROJECT_ID or "not_set",
            "location": GCP_LOCATION,
            "model": VERTEX_MODEL_RESOURCE_NAME or "NOT SET ⚠️",
            "service_account": VERTEX_SERVICE_ACCOUNT or "default (not set) ⚠️",
            "gcs_bucket": GCS_BUCKET_NAME,
            "input_prefix": GCS_INPUT_LIST_PREFIX,
            "output_prefix": GCS_OUTPUT_PREFIX,
        },
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)