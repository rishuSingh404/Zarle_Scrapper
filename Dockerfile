# 1) Use a slim Python image
FROM python:3.11-slim

# 2) Install headless Chromium & Chromedriver
RUN apt-get update && apt-get install -y \
      chromium \
      chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 3) Tell Selenium where to find them
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 4) Copy requirements & install Python deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Copy all your code
COPY . .

# 6) Expose Streamlit’s default port
EXPOSE 8501

# 7) Launch the Streamlit app
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
