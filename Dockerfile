# ── 1) Base image ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── 2) Install Chromium + libs ───────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
      chromium \
      fonts-liberation \
      libnss3 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium

# ── 3) Python deps ────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 4) Copy code ───────────────────────────────────────────────────────────────
COPY . .

# ── 5) Expose & launch on Railway’s assigned port ─────────────────────────────
EXPOSE 8501
CMD ["sh","-c","streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port $PORT"]
