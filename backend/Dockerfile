FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip first to avoid hash-check bugs in older pip
RUN pip install --upgrade pip

# Install CPU-only PyTorch (~200 MB vs ~2 GB for the default GPU wheel).
# Must be done before requirements.txt so sentence-transformers picks it up.
RUN pip install --no-cache-dir \
    torch==2.3.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==21.2.0 PyJWT==2.9.0 groq

# Copy application code
COPY . .

RUN mkdir -p uploads keyframes data

EXPOSE 8000

CMD gunicorn app.main:app \
      -k uvicorn.workers.UvicornWorker \
      -w ${WEB_WORKERS:-2} \
      --bind 0.0.0.0:8000 \
      --graceful-timeout 30 \
      --timeout 120 \
      --keep-alive 5 \
      --access-logfile - \
      --error-logfile -
