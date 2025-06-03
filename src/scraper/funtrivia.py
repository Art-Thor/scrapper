import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import re
from playwright.async_api import Browser, Page, BrowserContext
from .base import BaseScraper

class FunTriviaScraper(BaseScraper):
    def __init__(self, config_path: str = "config/settings.json"):
        super().__init__(config_path)
        self.mappings = self._load_mappings()
        self.question_counter = {
            "multiple_choice": 0,
            "true_false": 0,
            "sound": 0
        }

    def _load_mappings(self) -> Dict[str, Any]:
        """Load mappings from JSON file."""
        with open("config/mappings.json", 'r') as f:
            return json.load(f)

    async def initialize(self) -> None:
        """Initialize the scraper with a browser instance."""
        from playwright.async_api import async_playwright
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self._ensure_directories()

    async def close(self) -> None:
        """Close the browser instance."""
        if self.browser:
            await self.browser.close()

    async def scrape_questions(self, max_questions: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape questions from FunTrivia.com."""
        if not self.browser:
            await self.initialize()

        questions = []
        categories = await self._get_categories()
        
        for category in categories:
            if max_questions and len(questions) >= max_questions:
                break
                
            quiz_links = await self._get_quiz_links(category)
            for quiz_link in quiz_links:
                if max_questions and len(questions) >= max_questions:
                    break
                    
                quiz_questions = await self._scrape_quiz(quiz_link)
                questions.extend(quiz_questions)
                await self._random_delay()

        return questions

    async def _get_categories(self) -> List[str]:
        """Get all category URLs from the main page."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            await page.goto(f"{self.config['scraper']['base_url']}/quizzes/")
            categories = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/quizzes/"]'));
                    return links.map(link => link.href);
                }
            """)
            return list(set(categories))  # Remove duplicates
        finally:
            await context.close()

    async def _get_quiz_links(self, category_url: str) -> List[str]:
        """Get all quiz links from a category page."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            await page.goto(category_url)
            quiz_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/quiz/"]'));
                    return links.map(link => link.href);
                }
            """)
            return list(set(quiz_links))  # Remove duplicates
        finally:
            await context.close()

    async def _scrape_quiz(self, quiz_url: str) -> List[Dict[str, Any]]:
        """Scrape all questions from a quiz."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            await page.goto(quiz_url)
            
            # Get quiz metadata
            difficulty = await self._get_quiz_difficulty(page)
            domain = await self._get_quiz_domain(page)
            topic = await self._get_quiz_topic(page)
            
            # Start the quiz
            await page.click('button:has-text("Start Quiz")')
            
            questions = []
            while True:
                # Check if we're at the end of the quiz
                if await page.query_selector('text="Quiz Complete"'):
                    break
                
                # Get current question
                question_data = await self._extract_question_data(page)
                if question_data:
                    question_data.update({
                        "difficulty": self.map_difficulty(difficulty),
                        "domain": self.map_domain(domain),
                        "topic": self.map_topic(topic)
                    })
                    questions.append(question_data)
                
                # Answer the question (always choose first option to proceed)
                await page.click('input[type="radio"]')
                await page.click('button:has-text("Submit")')
                await self._random_delay()
            
            return questions
        finally:
            await context.close()

    async def _extract_question_data(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract question data from the current page."""
        try:
            # Get question text
            question_text = await page.evaluate("""
                () => document.querySelector('.question-text').textContent
            """)
            
            # Get answer options
            options = await page.evaluate("""
                () => {
                    const options = Array.from(document.querySelectorAll('.answer-option'));
                    return options.map(opt => opt.textContent.trim());
                }
            """)
            
            # Check for media
            has_image = await page.query_selector('img.question-image')
            has_audio = await page.query_selector('audio')
            
            # Determine question type
            if has_audio:
                question_type = "sound"
            elif len(options) == 2 and all(opt.lower() in ["true", "false"] for opt in options):
                question_type = "true_false"
            else:
                question_type = "multiple_choice"
            
            # Generate question ID
            self.question_counter[question_type] += 1
            question_id = f"Question_{question_type.upper()}_Parsed_{self.question_counter[question_type]:04d}"
            
            # Download media if present
            media_path = None
            if has_image:
                image_url = await page.evaluate("""
                    () => document.querySelector('img.question-image').src
                """)
                media_path = await self.download_media(image_url, "image", question_id)
            elif has_audio:
                audio_url = await page.evaluate("""
                    () => document.querySelector('audio').src
                """)
                media_path = await self.download_media(audio_url, "audio", question_id)
            
            return {
                "id": question_id,
                "type": question_type,
                "question": question_text,
                "options": options,
                "media_path": media_path
            }
        except Exception as e:
            self.logger.error(f"Error extracting question data: {e}")
            return None

    async def _get_quiz_difficulty(self, page: Page) -> str:
        """Get the quiz difficulty level."""
        try:
            difficulty = await page.evaluate("""
                () => {
                    const diff = document.querySelector('.difficulty-level');
                    return diff ? diff.textContent.trim() : 'Average';
                }
            """)
            return difficulty
        except:
            return "Average"

    async def _get_quiz_domain(self, page: Page) -> str:
        """Get the quiz domain/category."""
        try:
            domain = await page.evaluate("""
                () => {
                    const breadcrumbs = Array.from(document.querySelectorAll('.breadcrumb-item'));
                    return breadcrumbs[1] ? breadcrumbs[1].textContent.trim() : 'General';
                }
            """)
            return domain
        except:
            return "General"

    async def _get_quiz_topic(self, page: Page) -> str:
        """Get the quiz topic/subcategory."""
        try:
            topic = await page.evaluate("""
                () => {
                    const breadcrumbs = Array.from(document.querySelectorAll('.breadcrumb-item'));
                    return breadcrumbs[2] ? breadcrumbs[2].textContent.trim() : 'General';
                }
            """)
            return topic
        except:
            return "General"

    async def download_media(self, url: str, media_type: str, question_id: str) -> str:
        """Download media file and return the local path."""
        import aiohttp
        import os
        
        # Determine file extension and directory
        ext = url.split('.')[-1].lower()
        if media_type == "image":
            directory = self.config['storage']['images_dir']
            filename = f"{question_id}.{ext}"
        else:  # audio
            directory = self.config['storage']['audio_dir']
            filename = f"{question_id}.{ext}"
        
        filepath = os.path.join(directory, filename)
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
                    return filepath
        
        return None

    def map_difficulty(self, raw_difficulty: str) -> str:
        """Map FunTrivia difficulty to standardized value."""
        for std_difficulty, raw_values in self.mappings['difficulty_mapping'].items():
            if raw_difficulty in raw_values:
                return std_difficulty
        return "Normal"  # Default to Normal if no match

    def map_domain(self, raw_domain: str) -> str:
        """Map FunTrivia domain to standardized value."""
        for std_domain, raw_values in self.mappings['domain_mapping'].items():
            if raw_domain in raw_values:
                return std_domain
        return "Culture"  # Default to Culture if no match

    def map_topic(self, raw_topic: str) -> str:
        """Map FunTrivia topic to standardized value."""
        for std_topic, raw_values in self.mappings['topic_mapping'].items():
            if raw_topic in raw_values:
                return std_topic
        return "General"  # Default to General if no match 