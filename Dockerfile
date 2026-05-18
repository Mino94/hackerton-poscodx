# 전체 AutoPM(Streamlit + CrewAI)을 공개 URL에서 구동하기 위한 컨테이너 — Render/Fly/Railway 등에서 사용.
# Vercel 서버리스와 달리 장시간 프로세스가 가능하다.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    PYTHONUTF8=1

WORKDIR /app

# 일부 네이티브 휠 빌드·헬스체크용
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p outputs

EXPOSE 8501

# Streamlit 내장 헬스 엔드포인트 — 오케스트레이터가 준비 여부를 판별할 때 쓴다.
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501"]
