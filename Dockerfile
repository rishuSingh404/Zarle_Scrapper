# 1) Base image
FROM python:3.11-slim

# 2) Install Chromium + minimal deps for headless
RUN apt-get update && apt-get install -y \
      chromium \
      fonts-liberation \
      libnss3 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# 3) Tell Selenium where to find Chrome
ENV CHROME_BIN=/usr/bin/chromium

# 4) Install Python deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Copy your app
COPY . .

# 6) Expose Streamlit port and run
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
