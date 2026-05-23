FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright's Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

ENV PYTHONUNBUFFERED=1
ENV OUTPUT_DIR=/app/outputs
ENV CHROMA_PERSIST_DIR=/app/chroma_db

RUN mkdir -p /app/outputs /app/chroma_db

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
