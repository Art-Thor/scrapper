# FunTrivia Quiz Scraper

A robust web scraper designed to extract quiz questions from FunTrivia.com and organize them into a structured knowledge base.

## Features

- Scrapes multiple choice, true/false, and sound-based questions
- Downloads and indexes associated images and audio files
- Maps categories and difficulties to standardized values
- Supports concurrent scraping for high throughput
- Exports data to CSV files matching provided templates
- Optional Google Sheets integration
- Docker support for easy deployment

## Project Structure

```
.
├── README.md
├── requirements.txt
├── Dockerfile
├── config/
│   ├── mappings.json
│   └── settings.json
├── src/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── funtrivia.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── question.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── browser.py
│   │   ├── storage.py
│   │   └── sheets.py
│   └── main.py
└── assets/
    ├── images/
    └── audio/
```

## Setup

### Local Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Create a `.env` file with your configuration:
```bash
cp .env.example .env
# Edit .env with your settings
```

### Docker

1. Build the Docker image:
```bash
docker build -t funtrivia-scraper .
```

2. Run the scraper:
```bash
docker run -v $(pwd)/output:/app/output funtrivia-scraper
```

## Usage

### Basic Usage

```bash
python src/main.py
```

### Advanced Options

```bash
python src/main.py --max-questions 1000 --concurrency 5 --categories "History,Science"
```

## Configuration

The scraper uses two main configuration files:

1. `config/mappings.json`: Contains mappings for:
   - Difficulty levels
   - Domains
   - Topics

2. `config/settings.json`: Contains general settings:
   - Concurrency level
   - Rate limiting
   - Output paths
   - Google Sheets integration

## Output

The scraper generates three CSV files:
1. `multiple_choice.csv`: Multiple choice questions
2. `true_false.csv`: True/False questions
3. `sound.csv`: Sound-based questions

Media files are saved in:
- `assets/images/`: Question images
- `assets/audio/`: Audio files

## Google Sheets Integration

To enable Google Sheets integration:

1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create service account credentials
4. Download the JSON key file
5. Share your Google Sheet with the service account email
6. Set `GOOGLE_SHEETS_ENABLED=true` in `.env`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License 