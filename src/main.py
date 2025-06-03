import asyncio
import argparse
import json
import pandas as pd
from pathlib import Path
from scraper.funtrivia import FunTriviaScraper

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='FunTrivia Quiz Scraper')
    parser.add_argument('--max-questions', type=int, help='Maximum number of questions to scrape')
    parser.add_argument('--concurrency', type=int, help='Number of concurrent scrapers')
    parser.add_argument('--categories', type=str, help='Comma-separated list of categories to scrape')
    args = parser.parse_args()

    # Load configuration
    with open('config/settings.json', 'r') as f:
        config = json.load(f)

    # Update config with command line arguments
    if args.max_questions:
        config['scraper']['max_questions_per_run'] = args.max_questions
    if args.concurrency:
        config['scraper']['concurrency'] = args.concurrency

    # Initialize scraper
    scraper = FunTriviaScraper()
    await scraper.initialize()

    try:
        # Scrape questions
        questions = await scraper.scrape_questions(
            max_questions=config['scraper']['max_questions_per_run']
        )

        # Group questions by type
        questions_by_type = {
            'multiple_choice': [],
            'true_false': [],
            'sound': []
        }

        for question in questions:
            questions_by_type[question['type']].append(question)

        # Save questions to CSV files
        for question_type, type_questions in questions_by_type.items():
            if not type_questions:
                continue

            # Convert to DataFrame
            df = pd.DataFrame(type_questions)
            
            # Save to CSV
            output_file = Path(config['storage']['output_dir']) / config['storage']['csv_files'][question_type]
            df.to_csv(output_file, index=False)
            print(f"Saved {len(type_questions)} {question_type} questions to {output_file}")

    finally:
        # Clean up
        await scraper.close()

if __name__ == '__main__':
    asyncio.run(main()) 