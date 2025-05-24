# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── OS packages: headless Chromium + minimal fonts (NO chromedriver) ─────────
RUN apt-get update && apt-get install -y \
        chromium \
        fonts-liberation \
        libnss3 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Tell Selenium where the browser binary is
ENV CHROME_BIN=/usr/bin/chromium

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App code & launch command ────────────────────────────────────────────────
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
