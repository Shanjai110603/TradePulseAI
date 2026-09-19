# TradePulse Lightweight 24/7 VPS Daemon Container
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY core/ core/
COPY ui/ ui/
COPY main.py .

# Run 24/7 in headless daemon mode
CMD ["python", "main.py", "--headless"]
