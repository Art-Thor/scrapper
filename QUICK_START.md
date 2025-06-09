# 🚀 FunTrivia Scraper - Quick Start Guide

## 📦 What is this?
A high-performance web scraper for FunTrivia.com with batch processing, Docker support, and multiple speed profiles.

## ⚡ Quick Start

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Basic scraping (50 questions)
python src/main.py --max-questions 50

# Fast scraping with specific categories
python src/main.py --categories entertainment,movies --speed-profile fast --max-questions 100
```

### Docker Setup

#### Docker Compose (Recommended)
```bash
# Safe batch mode (default)
docker-compose up funtrivia-scraper

# Fast batch mode
docker-compose --profile fast up funtrivia-fast

# Single scraping mode
docker-compose --profile single up funtrivia-single

# Monitor mode
docker-compose --profile monitoring up funtrivia-monitor

# Build and run in background
docker-compose up -d funtrivia-scraper
```

#### Manual Docker
```bash
# Build image
docker build -t funtrivia-scraper .

# Run batch scraper (safe mode)
docker run -v $(pwd)/output:/app/output -v $(pwd)/assets:/app/assets funtrivia-scraper

# Run with custom parameters
docker run -v $(pwd)/output:/app/output -v $(pwd)/assets:/app/assets funtrivia-scraper \
  --mode batch --batch-size 3 --parallel-jobs 2 --questions-per-batch 100

# Monitor mode
docker run -v $(pwd)/output:/app/output -v $(pwd)/logs:/app/logs funtrivia-scraper --mode monitor

# Single scraping mode
docker run -v $(pwd)/output:/app/output funtrivia-scraper \
  --mode single --max-questions 200 --categories "entertainment,movies" --speed-profile fast
```

## 🔧 Configuration

### Speed Profiles
- `normal`: 130-200 q/hour (safe, default)
- `fast`: 200-350 q/hour (balanced)
- `aggressive`: 350-500 q/hour (high performance)

### Batch Processing
```bash
# Safe batch processing
python tools/batch_scraper.py --batch-size 2 --parallel-jobs 1 --questions-per-batch 50

# Performance batch processing
python tools/batch_scraper.py --batch-size 4 --parallel-jobs 3 --questions-per-batch 200 --speed-profile fast
```

## 📊 File Structure
```
output/           # CSV files with scraped data
assets/           # Downloaded images and audio
logs/             # Scraping logs
config/           # Settings and mappings
tools/            # Batch processing scripts
```

## 🎯 Key Features
- **Batch Processing**: Process multiple categories in parallel
- **Speed Profiles**: Optimize for speed vs safety
- **Docker Support**: Easy deployment and scaling
- **Resume Capability**: Continue from failed batches
- **Multiple Formats**: CSV export, Google Sheets integration
- **Smart Filtering**: Skip incompatible quiz types
- **Media Downloads**: Images and audio files

## 🚨 Important Notes
- Start with `normal` speed profile for testing
- Monitor logs for errors: `tail -f logs/scraper.log`
- Respect the website's terms of service
- Use timeouts for long-running operations

## 📈 Performance Tips
1. **For best results**: Use batch processing with 2-4 parallel jobs
2. **For stability**: Keep batch-size ≤ 3, parallel-jobs ≤ 2  
3. **For speed**: Use `fast` profile with proper timeouts
4. **For monitoring**: Check `scraping_metrics.json` for performance data

## 🐳 Docker Improvements
- **Multi-mode support**: batch, single, monitor, health check
- **Security**: Non-root user execution
- **Health checks**: Automatic container monitoring
- **Volume mounting**: Persistent data storage
- **Easy scaling**: Docker Compose profiles for different use cases

## 🔧 Recent Updates
- ✅ Removed Russian text from code (English-only codebase)
- ✅ Enhanced Dockerfile with batch processing support
- ✅ Added docker-entrypoint.py with multiple operation modes
- ✅ Created Docker Compose with service profiles
- ✅ Improved timeout settings for better performance
- ✅ Added health checks and monitoring capabilities

---
*Last updated: June 2025* 