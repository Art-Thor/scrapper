# FunTrivia Batch Scraper Docker Image
FROM python:3.11-slim

# Metadata
LABEL maintainer="FunTrivia Scraper"
LABEL description="Web scraper with batch processing support for FunTrivia.com"
LABEL version="2.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Basic tools
    wget curl gnupg ca-certificates \
    # Build tools for package compilation
    gcc python3-dev build-essential \
    # Playwright/Chromium libraries
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 \
    libdrm2 libxkbcommon0 libpango-1.0-0 \
    libcairo2 libasound2 \
    # Monitoring utilities
    htop procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file for Docker cache optimization
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application source code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p output assets/images assets/audio logs credentials && \
    chmod 755 output assets logs && \
    chmod 777 assets/images assets/audio

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Healthcheck for monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Create user for security
RUN useradd -m -u 1000 scraper && \
    chown -R scraper:scraper /app
USER scraper

# Entry point with support for different modes
ENTRYPOINT ["python", "docker-entrypoint.py"]

# Default parameters - run batch scraper in safe mode
CMD ["--mode", "batch", "--batch-size", "2", "--parallel-jobs", "1", "--questions-per-batch", "50"]