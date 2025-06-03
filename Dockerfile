# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p output assets/images assets/audio

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the scraper
CMD ["python", "src/main.py"] 