FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu118
RUN python -c "import whisper; whisper.load_model('medium')"
RUN python -c "from pyannote.audio import Pipeline; Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', token='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')"

COPY api_worker.py .

EXPOSE 8080
ENV HF_HUB_OFFLINE=1

CMD ["uvicorn", "api_worker:app", "--host", "0.0.0.0", "--port", "8080"]
