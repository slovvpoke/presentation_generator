# Use Python 3.9 slim image# Use Python 3.9 slim image

FROM python:3.9-slimFROM python:3.9-slim



# Install system dependencies for Chrome and Selenium# Install system dependencies for Chrome and Selenium

RUN apt-get update && apt-get install -y \RUN apt-get update && apt-get install -y \

    wget \    wget \

    gnupg \    gnupg \

    unzip \    unzip \

    curl \    curl \

    xvfb \    xvfb \

    ca-certificates \    ca-certificates \

    fonts-liberation \    fonts-liberation \

    libasound2 \    libasound2 \

    libatk-bridge2.0-0 \    libatk-bridge2.0-0 \

    libatk1.0-0 \    libatk1.0-0 \

    libatspi2.0-0 \    libatspi2.0-0 \

    libdrm2 \    libdrm2 \

    libgtk-3-0 \    libgtk-3-0 \

    libnspr4 \    libnspr4 \

    libnss3 \    libnss3 \

    libxcomposite1 \    libxcomposite1 \

    libxdamage1 \    libxdamage1 \

    libxfixes3 \    libxfixes3 \

    libxrandr2 \    libxrandr2 \

    libxss1 \    libxss1 \

    libxtst6 \    libxtst6 \

    lsb-release \    lsb-release \

    && rm -rf /var/lib/apt/lists/*    && rm -rf /var/lib/apt/lists/*



# Install Google Chrome# Install Google Chrome

RUN wget -q -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \RUN wget -q -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \

    && apt-get update \    && apt-get update \

    && apt-get install -y ./google-chrome.deb \    && apt-get install -y ./google-chrome.deb \

    && rm google-chrome.deb \    && rm google-chrome.deb \

    && rm -rf /var/lib/apt/lists/*    && rm -rf /var/lib/apt/lists/*



# Set working directory# Set working directory

WORKDIR /appWORKDIR /app



# Copy requirements and install Python dependencies# Copy requirements and install Python dependencies

COPY requirements.txt .COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txtRUN pip install --no-cache-dir -r requirements.txt



# Copy application code# Copy application code

COPY . .COPY . .



# Create necessary directories# Create necessary directories

RUN mkdir -p uploads static templatesRUN mkdir -p uploads static templates



# Set environment variables for production# Set environment variables for production

ENV PYTHONPATH=/appENV PYTHONPATH=/app

ENV RENDER=trueENV RENDER=true

ENV CHROME_BIN=/usr/bin/google-chromeENV CHROME_BIN=/usr/bin/google-chrome

ENV DISPLAY=:99ENV DISPLAY=:99



# Expose port# Expose port

EXPOSE 10000EXPOSE 10000



# Start command# Start command

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120", "app:app"]CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "120", "app:app"]