# FunTrivia Quiz Scraper

A comprehensive web scraper for extracting quiz questions from FunTrivia.com with support for multiple question types, automatic media downloads, and Google Sheets integration.

## 🚀 Features

- **Multiple Question Types**: Supports multiple choice, true/false, and sound-based questions
- **Smart Answer Detection**: Automatically identifies correct answers and extracts hints/explanations
- **Media Handling**: Downloads and manages images and audio files with standardized paths
- **Concurrent Scraping**: Configurable concurrency with rate limiting to prevent IP bans
- **Google Sheets Integration**: Automatic upload to Google Sheets with proper worksheet organization
- **Robust Error Handling**: Comprehensive retry mechanisms and detailed logging
- **CSV Export**: Standardized CSV output matching specific template formats
- **Docker Support**: Easy deployment with containerization
- **Persistent Indexing**: Maintains question numbering across multiple runs
- **Append Mode**: Adds new questions to existing CSV files without overwriting

## 📁 Project Structure

```
Trivio_scrapper/
├── src/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── base.py                 # Base scraper interface
│   │   └── funtrivia.py           # FunTrivia-specific implementation
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── rate_limiter.py        # Request rate limiting
│   │   ├── sheets.py              # Google Sheets integration
│   │   ├── csv_handler.py         # CSV append/overwrite handling
│   │   └── indexing.py            # Persistent question indexing
│   └── main.py                    # Main script
├── config/
│   ├── settings.json              # General configuration
│   └── mappings.json             # Category/difficulty mappings
├── output/                        # CSV output files
├── assets/
│   ├── images/                    # Downloaded images
│   └── audio/                     # Downloaded audio files
├── logs/                          # Application logs
├── question_indices.json         # Persistent question indices
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
└── README.md                      # This file
```

## 🛠️ Installation & Setup

### Option 1: Local Development Setup

#### Prerequisites
- Python 3.11+
- pip
- Git

#### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Trivio_scrapper
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Create required directories**
   ```bash
   mkdir -p output assets/images assets/audio logs
   ```

6. **Configure the application**
   ```bash
   # Copy and edit configuration files
   cp config/settings.json.example config/settings.json
   cp config/mappings.json.example config/mappings.json
   ```

7. **Run the scraper**
   ```bash
   python src/main.py --max-questions 100 --concurrency 3
   ```

### Option 2: Docker Setup

#### Prerequisites
- Docker
- Docker Compose (optional)

#### Docker Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Trivio_scrapper
   ```

2. **Build Docker image**
   ```bash
   docker build -t funtrivia-scraper .
   ```

3. **Run with Docker**
   ```bash
   # Basic run
   docker run -v $(pwd)/output:/app/output funtrivia-scraper --max-questions 100

   # With custom parameters
   docker run -v $(pwd)/output:/app/output funtrivia-scraper --max-questions 500 --concurrency 5

   # With Google Sheets (mount credentials)
   docker run -v $(pwd)/output:/app/output \
              -v $(pwd)/credentials:/app/credentials \
              funtrivia-scraper
   ```

## ⚙️ Configuration

### Settings.json Configuration

Edit `config/settings.json` to customize the scraper behavior:

```json
{
  "scraper": {
    "base_url": "https://www.funtrivia.com",
    "max_questions_per_run": 1000,
    "concurrency": 3,
    "rate_limit": {
      "requests_per_minute": 30
    },
    "delays": {
      "min": 1,
      "max": 3
    }
  },
  "storage": {
    "output_dir": "output",
    "images_dir": "assets/images",
    "audio_dir": "assets/audio",
    "csv_files": {
      "multiple_choice": "multiple_choice.csv",
      "true_false": "true_false.csv",
      "sound": "sound.csv"
    }
  },
  "google_sheets": {
    "enabled": false,
    "credentials_file": "credentials/service-account.json",
    "spreadsheet_id": "your_spreadsheet_id_here"
  },
  "logging": {
    "level": "INFO",
    "file": "logs/scraper.log"
  }
}
```

### Google Sheets Setup

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable Google Sheets API**
   - Navigate to APIs & Services > Library
   - Search for "Google Sheets API" and enable it

3. **Create Service Account**
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "Service Account"
   - Fill in service account details
   - Download the JSON key file

4. **Setup Credentials**
   ```bash
   mkdir -p credentials
   # Copy your service account JSON file to credentials/service-account.json
   ```

5. **Create Google Spreadsheet**
   - Create a new Google Spreadsheet
   - Share it with your service account email (found in the JSON file)
   - Copy the spreadsheet ID from the URL

6. **Update Configuration**
   ```json
   {
     "google_sheets": {
       "enabled": true,
       "credentials_file": "credentials/service-account.json",
       "spreadsheet_id": "1abc123def456ghi789jkl_your_spreadsheet_id"
     }
   }
   ```

## 🎯 Usage Examples

### Basic Usage

```bash
# Scrape 100 questions with default settings (append mode)
python src/main.py --max-questions 100

# Use higher concurrency for faster scraping
python src/main.py --max-questions 500 --concurrency 5

# Overwrite existing CSV files instead of appending
python src/main.py --max-questions 200 --overwrite

# Create backup before overwriting
python src/main.py --max-questions 200 --overwrite --backup

# Reset question indices to start from 0
python src/main.py --reset-indices

# Specify custom config file
python src/main.py --config my-config.json --max-questions 200
```

### Docker Usage

```bash
# Basic Docker run
docker run -v $(pwd)/output:/app/output funtrivia-scraper --max-questions 100

# With environment variables
docker run -e MAX_QUESTIONS=1000 \
           -v $(pwd)/output:/app/output \
           funtrivia-scraper

# With docker-compose
docker-compose up
```

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--max-questions` | Maximum questions to scrape | 1000 |
| `--concurrency` | Number of concurrent scrapers | 3 |
| `--config` | Path to configuration file | config/settings.json |
| `--categories` | Comma-separated category list | All categories |
| `--append` | Append to existing CSV files | True |
| `--overwrite` | Overwrite existing CSV files | False |
| `--backup` | Create backup before overwriting | False |
| `--reset-indices` | Reset question indices to 0 | False |

## 📊 Output Format

### CSV Files

The scraper generates three CSV files:

1. **multiple_choice.csv** - Multiple choice questions
2. **true_false.csv** - True/false questions  
3. **sound.csv** - Audio-based questions

### CSV Structure

#### Multiple Choice Questions
```csv
Key,Domain,Topic,Difficulty,Question,Option1,Option2,Option3,Option4,CorrectAnswer,Hint,ImagePath
Question_MQ_Parsed_0001,Culture,General,Normal,"What is...?",Option A,Option B,Option C,Option D,Option A,Explanation here,assets/images/Question_MQ_Parsed_0001.jpg
```

#### True/False Questions
```csv
Key,Domain,Topic,Difficulty,Question,Option1,Option2,CorrectAnswer,Hint
Question_TF_Parsed_0001,Science,Biology,Hard,"The Earth is flat",True,False,False,The Earth is actually round
```

#### Sound Questions
```csv
Key,Domain,Topic,Difficulty,Question,Option1,Option2,Option3,Option4,CorrectAnswer,Hint,AudioPath
Question_SOUND_Parsed_0001,Entertainment,Music,Normal,"What song is this?",Song A,Song B,Song C,Song D,Song A,Famous hit from 1990s,assets/audio/Question_SOUND_Parsed_0001.mp3
```

## 🐛 Comprehensive Troubleshooting Guide

### Common Issues and Solutions

#### 1. Playwright Installation and Browser Issues

**Problem**: `playwright: command not found` or browser download fails
```
Error installing playwright
Error downloading browsers
Chromium executable not found
```

**Solutions**:
```bash
# Complete reinstallation
pip uninstall playwright
pip install playwright==1.42.0
playwright install chromium

# For Linux users - install system dependencies
sudo apt-get update
sudo apt-get install -y libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libdrm2 libgtk-3-0 libgbm1 libasound2

# For Docker users - ensure browser installation in container
RUN playwright install chromium
RUN playwright install-deps chromium

# Check installation
python -c "import playwright; print('Playwright installed successfully')"
```

**Advanced Playwright Troubleshooting**:
```bash
# Set browser path manually if needed
export PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers

# Debug browser launch issues
python -c "
import asyncio
from playwright.async_api import async_playwright

async def test():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False)
    page = await browser.new_page()
    await page.goto('https://example.com')
    print('Browser test successful')
    await browser.close()

asyncio.run(test())
"
```

#### 2. Permission and Directory Issues

**Problem**: Cannot create directories or write files
```
PermissionError: [Errno 13] Permission denied
FileNotFoundError: [Errno 2] No such file or directory
```

**Solutions**:
```bash
# Fix permissions for existing directories
chmod -R 755 output/ assets/ logs/
sudo chown -R $USER:$USER output/ assets/ logs/

# Create directories manually with proper permissions
mkdir -p output assets/images assets/audio logs
chmod 755 output assets assets/images assets/audio logs

# For Docker users - set proper user in Dockerfile
USER 1000:1000
# or
RUN adduser --disabled-password --gecos '' scraper
USER scraper
```

#### 3. Google Sheets Authentication Failures

**Problem**: Authentication errors with Google Sheets API
```
oauth2client.client.HttpAccessTokenRefreshError
gspread.exceptions.APIError: [403] The caller does not have permission
File not found: credentials/service-account.json
```

**Solutions**:

1. **Verify Credentials File**:
```bash
# Check file exists and has correct permissions
ls -la credentials/service-account.json
chmod 600 credentials/service-account.json

# Validate JSON structure
python -c "import json; json.load(open('credentials/service-account.json'))"
```

2. **Test Authentication**:
```bash
python -c "
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(
    'credentials/service-account.json', scope)
client = gspread.authorize(creds)
print('Authentication successful!')
print(f'Service account email: {creds.service_account_email}')
"
```

3. **Common Setup Issues**:
```bash
# Ensure Google Sheets API is enabled
# Share spreadsheet with service account email
# Copy correct spreadsheet ID from URL
# https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

#### 4. Rate Limiting and IP Blocking

**Problem**: Getting blocked or rate limited by FunTrivia
```
HTTP 429: Too Many Requests
HTTP 403: Forbidden
Timeout errors
Connection refused
```

**Solutions**:

1. **Reduce Scraping Intensity**:
```json
{
  "scraper": {
    "concurrency": 1,
    "rate_limit": {
      "requests_per_minute": 15
    }
  }
}
```

2. **Add Random Delays**:
```json
{
  "scraper": {
    "delays": {
      "min": 3,
      "max": 8
    }
  }
}
```

3. **Use Different User Agents**:
```json
{
  "scraper": {
    "user_agents": [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    ]
  }
}
```

4. **Implement IP Rotation** (Advanced):
```python
# Add proxy support in browser context
context = await browser.new_context(
    proxy={"server": "http://proxy-server:port"}
)
```

#### 5. Memory and Performance Issues

**Problem**: Out of memory errors or poor performance
```
MemoryError: Unable to allocate memory
Process killed (OOM)
Very slow scraping speeds
```

**Solutions**:

1. **Reduce Concurrency**:
```bash
python src/main.py --concurrency 1 --max-questions 100
```

2. **Process in Smaller Batches**:
```bash
# Scrape in batches of 100
for i in {1..10}; do
    python src/main.py --max-questions 100
    sleep 60
done
```

3. **Docker Memory Limits**:
```bash
# Set memory limit for Docker
docker run --memory=2g --memory-swap=2g \
    -v $(pwd)/output:/app/output funtrivia-scraper
```

4. **Monitor Resource Usage**:
```bash
# Monitor memory usage
top -p $(pgrep -f "python src/main.py")

# Check disk space
df -h output/ assets/
```

#### 6. Network and Timeout Issues

**Problem**: Frequent network timeouts or connection errors
```
TimeoutError: Timeout 30000ms exceeded
NetworkError: net::ERR_CONNECTION_REFUSED
DNS resolution failed
```

**Solutions**:

1. **Increase Timeout Values**:
```json
{
  "scraper": {
    "timeout": 60000,
    "retries": 5
  }
}
```

2. **Check Network Connectivity**:
```bash
# Test basic connectivity
ping funtrivia.com
curl -I https://www.funtrivia.com/

# Check DNS resolution
nslookup funtrivia.com
```

3. **Use VPN if Region-Blocked**:
```bash
# Check if region blocked
curl -I https://www.funtrivia.com/ --header "X-Forwarded-For: US_IP"
```

#### 7. CSV and Data Issues

**Problem**: Malformed CSV output or incorrect data
```
ParserError: Error tokenizing data
UnicodeDecodeError: 'utf-8' codec can't decode
Missing or incorrect answers
Empty CSV files
```

**Solutions**:

1. **Validate CSV Structure**:
```python
import pandas as pd
try:
    df = pd.read_csv('output/multiple_choice.csv')
    print(f"CSV valid: {len(df)} rows, {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
except Exception as e:
    print(f"CSV error: {e}")
```

2. **Check Question Indexing**:
```python
# View current indices
python -c "
from src.utils.indexing import QuestionIndexer
indexer = QuestionIndexer()
print(indexer.get_all_indices())
"

# Reset if corrupted
python src/main.py --reset-indices
```

3. **Backup and Restore**:
```bash
# Create manual backup
cp output/multiple_choice.csv output/multiple_choice_backup.csv

# Restore from backup
cp output/multiple_choice_backup.csv output/multiple_choice.csv
```

#### 8. Configuration and Logging Issues

**Problem**: Configuration not loading or logging not working
```
FileNotFoundError: config/settings.json not found
Logging not appearing in console
Permission denied writing to log file
```

**Solutions**:

1. **Validate Configuration**:
```bash
# Check config file syntax
python -c "import json; json.load(open('config/settings.json'))"

# Use default config
python src/main.py --config config/settings.json
```

2. **Fix Logging Issues**:
```bash
# Create logs directory
mkdir -p logs
chmod 755 logs

# Test logging
python -c "
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')
logger.info('Logging test successful')
"
```

### Debugging and Diagnostic Commands

1. **Test Scraper Components**:
```bash
# Test browser initialization
python -c "
import asyncio
from src.scraper.funtrivia import FunTriviaScraper

async def test():
    scraper = FunTriviaScraper()
    await scraper.initialize()
    print('Scraper initialized successfully')
    await scraper.close()

asyncio.run(test())
"
```

2. **Check Dependencies**:
```bash
# Verify all packages installed
pip check
pip list | grep -E "(playwright|pandas|gspread)"
```

3. **Run with Debug Logging**:
```bash
# Enable debug mode
python src/main.py --max-questions 5 2>&1 | tee debug.log
```

4. **Test Network Components**:
```bash
# Test rate limiter
python -c "
import asyncio
from src.utils.rate_limiter import RateLimiter

async def test():
    limiter = RateLimiter(10)  # 10 requests per minute
    for i in range(3):
        async with limiter:
            print(f'Request {i+1} allowed')

asyncio.run(test())
"
```

### Performance Monitoring and Optimization

1. **Monitor Scraping Progress**:
```bash
# Watch log file in real-time
tail -f logs/scraper.log

# Monitor CSV growth
watch -n 10 "wc -l output/*.csv"
```

2. **Performance Profiling**:
```bash
# Run with profiling
python -m cProfile -o profile.stats src/main.py --max-questions 50

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

3. **Resource Usage Monitoring**:
```bash
# Monitor system resources
htop
iostat -x 1
free -h
```

## 📈 Performance Optimization

### Recommended Settings

**For Fast Scraping (Risk of blocking)**:
```json
{
  "concurrency": 8,
  "rate_limit": {"requests_per_minute": 60},
  "delays": {"min": 0.5, "max": 1}
}
```

**For Safe Scraping (Recommended)**:
```json
{
  "concurrency": 3,
  "rate_limit": {"requests_per_minute": 30},
  "delays": {"min": 1, "max": 3}
}
```

**For Conservative Scraping (Very safe)**:
```json
{
  "concurrency": 1,
  "rate_limit": {"requests_per_minute": 15},
  "delays": {"min": 2, "max": 5}
}
```

## 🔧 Development

### Adding New Scrapers

1. Create new scraper in `src/scraper/`
2. Inherit from `BaseScraper`
3. Implement required methods
4. Add configuration mappings

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Code Quality

```bash
# Install linting tools
pip install black isort flake8

# Format code
black src/
isort src/

# Check code quality
flake8 src/
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

- Create an issue for bug reports
- Check existing issues before creating new ones
- Provide detailed error messages and logs
- Include system information (OS, Python version, etc.)

## 🔄 Changelog

### v1.0.0
- Initial release
- FunTrivia scraper implementation
- Google Sheets integration
- Docker support
- Comprehensive error handling
- Persistent question indexing
- CSV append/overwrite modes
- Enhanced troubleshooting documentation 