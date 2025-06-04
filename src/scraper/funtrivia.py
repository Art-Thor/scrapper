import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import re
import logging
import random
import sys
import os
from playwright.async_api import Browser, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError # type: ignore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type # type: ignore

# Add the src directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from .base import BaseScraper
from ..utils.rate_limiter import RateLimiter
from ..utils.indexing import QuestionIndexer
from ..utils.question_classifier import QuestionClassifier
from ..utils.text_processor import TextProcessor
from ..constants import (
    TIMEOUTS, RATE_LIMITS, USER_AGENTS, DESCRIPTION_SELECTORS, 
    THRESHOLDS, DEFAULT_PATHS
)


class FunTriviaScraper(BaseScraper):
    """
    Enhanced FunTrivia scraper with improved question type detection,
    description extraction, and organized modular structure.
    """
    
    def __init__(self, config_path: str = None):
        config_path = config_path or DEFAULT_PATHS['config_file']
        super().__init__(config_path)
        
        # Initialize components
        self.mappings = self._load_mappings()
        self.indexer = QuestionIndexer()
        self.rate_limiter = RateLimiter(
            self.config['scraper']['rate_limit']['requests_per_minute']
        )
        self.question_classifier = QuestionClassifier()
        self.text_processor = TextProcessor()
        
        # Configuration
        self.strict_mapping = self.config.get('scraper', {}).get('strict_mapping', False)

    def _load_mappings(self) -> Dict[str, Any]:
        """Load mappings from JSON file."""
        try:
            mappings_path = DEFAULT_PATHS['mappings_file']
            with open(mappings_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load mappings: {e}")
            raise

    async def initialize(self) -> None:
        """Initialize the scraper with a browser instance."""
        try:
            from playwright.async_api import async_playwright # type: ignore
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self._ensure_directories()
            self.logger.info("Scraper initialized successfully")
            self.logger.info(f"Current question indices: {self.indexer.get_all_indices()}")
        except Exception as e:
            self.logger.error(f"Failed to initialize scraper: {e}")
            raise

    async def close(self) -> None:
        """Close the browser instance."""
        if self.browser:
            try:
                await self.browser.close()
                self.logger.info("Browser closed successfully")
                self.logger.info(f"Final question indices: {self.indexer.get_all_indices()}")
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")

    async def scrape_questions(self, max_questions: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape questions from FunTrivia.com."""
        if not self.browser:
            await self.initialize()

        questions = []
        try:
            categories = await self._get_categories()
            self.logger.info(f"Found {len(categories)} categories")
            
            # Process categories concurrently
            questions = await self._process_categories_concurrently(categories, max_questions)
            
            self.logger.info(f"Successfully scraped {len(questions)} questions")
            return questions
        except Exception as e:
            self.logger.error(f"Error during question scraping: {e}")
            raise

    async def _process_categories_concurrently(self, categories: List[str], max_questions: Optional[int]) -> List[Dict[str, Any]]:
        """Process categories concurrently with proper semaphore control."""
        questions = []
        semaphore = asyncio.Semaphore(self.config['scraper']['concurrency'])
        
        async def scrape_category(category: str) -> List[Dict[str, Any]]:
            async with semaphore:
                try:
                    quiz_links = await self._get_quiz_links(category)
                    self.logger.info(f"Found {len(quiz_links)} quizzes in category {category}")
                    
                    category_questions = []
                    for quiz_link in quiz_links:
                        if max_questions and len(questions) >= max_questions:
                            break
                        
                        async with self.rate_limiter:
                            quiz_questions = await self._scrape_quiz(quiz_link)
                            category_questions.extend(quiz_questions)
                            await self._random_delay()
                    
                    return category_questions
                except Exception as e:
                    self.logger.error(f"Error scraping category {category}: {e}")
                    return []

        # Execute concurrent scraping
        tasks = [scrape_category(category) for category in categories]
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        for category_questions in results:
            questions.extend(category_questions)
            if max_questions and len(questions) >= max_questions:
                questions = questions[:max_questions]
                break

        return questions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def _get_categories(self) -> List[str]:
        """Get all category URLs from the main page."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            async with self.rate_limiter:
                await page.goto(
                    f"{self.config['scraper']['base_url']}/quizzes/", 
                    timeout=TIMEOUTS['page_load']
                )
                await page.wait_for_load_state('networkidle', timeout=TIMEOUTS['network_idle'])
                
                categories = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/quizzes/"]'));
                        return links.map(link => link.href);
                    }
                """)
                return list(set(categories))  # Remove duplicates
        except PlaywrightTimeoutError:
            self.logger.error("Timeout while loading categories page")
            raise
        except Exception as e:
            self.logger.error(f"Error getting categories: {e}")
            raise
        finally:
            await context.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def _get_quiz_links(self, category_url: str) -> List[str]:
        """Get all quiz links from a category page."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            async with self.rate_limiter:
                await page.goto(category_url, timeout=TIMEOUTS['page_load'])
                await page.wait_for_load_state('networkidle', timeout=TIMEOUTS['network_idle'])
                
                quiz_links = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/quiz/"]'));
                        return links.map(link => link.href);
                    }
                """)
                return list(set(quiz_links))  # Remove duplicates
        except PlaywrightTimeoutError:
            self.logger.error(f"Timeout while loading category page: {category_url}")
            raise
        except Exception as e:
            self.logger.error(f"Error getting quiz links for {category_url}: {e}")
            raise
        finally:
            await context.close()

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((PlaywrightTimeoutError,))
    )
    async def _scrape_quiz(self, quiz_url: str) -> List[Dict[str, Any]]:
        """Scrape all questions from a quiz with descriptions."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            async with self.rate_limiter:
                await page.goto(quiz_url, timeout=TIMEOUTS['quiz_page'])
                await page.wait_for_load_state('networkidle', timeout=TIMEOUTS['quiz_wait'])
                
                # Get quiz metadata
                quiz_metadata = await self._extract_quiz_metadata(page)
                
                # Extract questions
                questions = await self._extract_questions_from_page(page)
                
                if not questions:
                    self.logger.warning(f"No questions found on quiz page: {quiz_url}")
                    return []
                
                # Get descriptions from results page
                descriptions = await self._extract_descriptions_from_results(page, questions)
                
                # Process and enhance questions
                processed_questions = self._process_extracted_questions(
                    questions, descriptions, quiz_metadata
                )
                
                self.logger.info(f"Successfully extracted {len(processed_questions)} questions with descriptions from {quiz_url}")
                return processed_questions
                
        except PlaywrightTimeoutError:
            self.logger.warning(f"Timeout while scraping quiz: {quiz_url}")
            return []
        except Exception as e:
            self.logger.error(f"Error scraping quiz {quiz_url}: {e}")
            return []
        finally:
            await context.close()

    async def _extract_quiz_metadata(self, page: Page) -> Dict[str, str]:
        """Extract metadata about the quiz."""
        return {
            'difficulty': await self._get_quiz_difficulty(page),
            'domain': await self._get_quiz_domain(page),
            'topic': await self._get_quiz_topic(page)
        }

    async def _extract_questions_from_page(self, page: Page) -> List[Dict[str, Any]]:
        """Extract questions using primary and fallback methods."""
        # Try primary extraction method
        questions = await self._extract_all_questions_from_page(page)
        
        if not questions:
            self.logger.warning("No questions found using primary extraction method")
            # Try alternative extraction method
            questions = await self._extract_questions_alternative(page)
        
        return questions

    def _process_extracted_questions(self, questions: List[Dict[str, Any]], descriptions: Dict[str, str], metadata: Dict[str, str]) -> List[Dict[str, Any]]:
        """Process and enhance extracted questions with metadata and descriptions."""
        processed_questions = []
        
        for i, question_data in enumerate(questions):
            if not question_data:
                continue
            
            # Classify question type using the dedicated classifier
            question_text = question_data['question']
            options = question_data['options']
            question_type = self.question_classifier.classify(question_text, options)
            question_data['type'] = question_type
            
            # Generate unique question ID
            question_id = self.indexer.get_next_id(question_type)
            
            # Add description if available
            question_number = question_data.get('questionNumber', str(i+1))
            description = descriptions.get(question_number, '')
            
            # Clean and process text fields
            cleaned_question = self.text_processor.clean_question_text(question_text)
            cleaned_description = self.text_processor.clean_description_text(description)
            
            # Update question data with all metadata
            question_data.update({
                "id": question_id,
                "question": cleaned_question,
                "difficulty": self.map_difficulty(metadata['difficulty']),
                "domain": self.map_domain(metadata['domain']),
                "topic": self.map_topic(metadata['topic']),
                "correct_answer": question_data.get('correct_answer', options[0] if options else ''),
                "hint": question_data.get('hint', ''),
                "description": cleaned_description
            })
            
            processed_questions.append(question_data)
            self.logger.debug(f"Processed question {i+1}: {cleaned_question[:50]}...")
        
        return processed_questions

    async def _get_quiz_difficulty(self, page: Page) -> str:
        """Get the quiz difficulty level - Updated selectors."""
        try:
            difficulty = await page.evaluate("""
                () => {
                    // Try multiple strategies to find difficulty
                    const strategies = [
                        // Look in quiz metadata or description
                        () => {
                            const meta = document.querySelector('.quiz-meta, .quiz-info, .quiz-details');
                            if (meta) {
                                const text = meta.textContent.toLowerCase();
                                if (text.includes('easy') || text.includes('beginner')) return 'Easy';
                                if (text.includes('hard') || text.includes('difficult') || text.includes('expert')) return 'Hard';
                                if (text.includes('medium') || text.includes('average') || text.includes('normal')) return 'Normal';
                            }
                            return null;
                        },
                        // Look in breadcrumbs or page title
                        () => {
                            const title = document.title.toLowerCase();
                            if (title.includes('easy')) return 'Easy';
                            if (title.includes('hard') || title.includes('difficult')) return 'Hard';
                            return 'Normal';
                        }
                    ];
                    
                    for (const strategy of strategies) {
                        const result = strategy();
                        if (result) return result;
                    }
                    
                    return 'Normal'; // Default
                }
            """)
            return difficulty
        except Exception as e:
            self.logger.debug(f"Error getting difficulty: {e}")
            return "Normal"

    async def _get_quiz_domain(self, page: Page) -> str:
        """Get the quiz domain/category - Updated selectors."""
        try:
            domain = await page.evaluate("""
                () => {
                    // Strategy 1: Look in URL path
                    const urlPath = window.location.pathname;
                    const pathParts = urlPath.split('/').filter(part => part && part !== 'quiz');
                    
                    if (pathParts.length > 0) {
                        const category = pathParts[0];
                        // Map common URL categories to domains
                        const categoryMap = {
                            'animals': 'Nature',
                            'science': 'Science',
                            'geography': 'Geography',
                            'history': 'History',
                            'sports': 'Sports',
                            'music': 'Culture',
                            'movies': 'Culture',
                            'literature': 'Culture',
                            'humanities': 'Culture',
                            'people': 'Culture'
                        };
                        
                        if (categoryMap[category]) {
                            return categoryMap[category];
                        }
                        
                        // Return capitalized category if not mapped
                        return category.charAt(0).toUpperCase() + category.slice(1);
                    }
                    
                    // Strategy 2: Look in page title for category hints
                    const title = document.title.toLowerCase();
                    if (title.includes('animal')) return 'Nature';
                    if (title.includes('science') || title.includes('tech')) return 'Science';
                    if (title.includes('geography') || title.includes('world')) return 'Geography';
                    if (title.includes('history')) return 'History';
                    if (title.includes('sport')) return 'Sports';
                    
                    return 'Culture'; // Default for entertainment/general content
                }
            """)
            return domain
        except Exception as e:
            self.logger.debug(f"Error getting domain: {e}")
            return "Culture"

    async def _get_quiz_topic(self, page: Page) -> str:
        """Get the quiz topic/subcategory - Updated selectors."""
        try:
            topic = await page.evaluate("""
                () => {
                    // Strategy 1: Extract from page title
                    const titleElement = document.querySelector('h1');
                    if (titleElement) {
                        let title = titleElement.textContent.trim();
                        // Remove common suffixes
                        title = title.replace(/\s*(trivia\s*)?quiz$/i, '').trim();
                        if (title.length > 3 && title.length < 50) {
                            return title;
                        }
                    }
                    
                    // Strategy 2: Get from document title
                    const docTitle = document.title;
                    const titleMatch = docTitle.match(/^([^|]+)/);
                    if (titleMatch) {
                        let title = titleMatch[1].trim();
                        title = title.replace(/\s*(trivia\s*)?quiz$/i, '').trim();
                        if (title.length > 3 && title.length < 50) {
                            return title;
                        }
                    }
                    
                    return 'General';
                }
            """)
            return topic
        except Exception as e:
            self.logger.debug(f"Error getting topic: {e}")
            return "General"

    async def download_media(self, url: str, media_type: str, question_id: str) -> Optional[str]:
        """Download media file and return the local path."""
        import aiohttp # type: ignore
        import os
        from urllib.parse import urlparse
        
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10)
        )
        async def download_with_retry():
            # Parse URL to get file extension
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('.')
            ext = path_parts[-1].lower() if len(path_parts) > 1 else 'jpg'
            
            # Ensure valid extension
            if media_type == "image" and ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                ext = 'jpg'
            elif media_type == "audio" and ext not in ['mp3', 'wav', 'ogg', 'm4a']:
                ext = 'mp3'
            
            # Determine directory and filename
            if media_type == "image":
                directory = self.config['storage']['images_dir']
                filename = f"{question_id}.{ext}"
            else:  # audio
                directory = self.config['storage']['audio_dir']
                filename = f"{question_id}.{ext}"
            
            filepath = os.path.join(directory, filename)
            
            # Download the file
            headers = {'User-Agent': self._get_random_user_agent()}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        os.makedirs(directory, exist_ok=True)
                        with open(filepath, 'wb') as f:
                            f.write(await response.read())
                        self.logger.info(f"Successfully downloaded {media_type} for {question_id}")
                        return f"assets/{media_type}s/{filename}"  # Return relative path for CSV
                    else:
                        raise Exception(f"Failed to download {media_type}: HTTP {response.status}")
        
        try:
            return await download_with_retry()
        except Exception as e:
            self.logger.error(f"Failed to download {media_type} for {question_id}: {e}")
            return None

    def map_difficulty(self, raw_difficulty: str) -> str:
        """Map FunTrivia difficulty to standardized value."""
        for std_difficulty, raw_values in self.mappings['difficulty_mapping'].items():
            if raw_difficulty.lower() in [v.lower() for v in raw_values]:
                return std_difficulty
        
        if self.strict_mapping:
            raise ValueError(f"Unknown difficulty level encountered: '{raw_difficulty}'. "
                           f"Please add this to the difficulty_mapping in config/mappings.json "
                           f"or run with --dump-categories-only to collect all categories first.")
        
        self.logger.warning(f"Unknown difficulty level: {raw_difficulty}, defaulting to Normal")
        return "Normal"

    def map_domain(self, raw_domain: str) -> str:
        """Map FunTrivia domain to standardized value."""
        for std_domain, raw_values in self.mappings['domain_mapping'].items():
            if raw_domain.lower() in [v.lower() for v in raw_values]:
                return std_domain
        
        if self.strict_mapping:
            raise ValueError(f"Unknown domain encountered: '{raw_domain}'. "
                           f"Please add this to the domain_mapping in config/mappings.json "
                           f"or run with --dump-categories-only to collect all categories first.")
        
        self.logger.warning(f"Unknown domain: {raw_domain}, defaulting to Culture")
        return "Culture"

    def map_topic(self, raw_topic: str) -> str:
        """Map FunTrivia topic to standardized value."""
        for std_topic, raw_values in self.mappings['topic_mapping'].items():
            if raw_topic.lower() in [v.lower() for v in raw_values]:
                return std_topic
        
        if self.strict_mapping:
            raise ValueError(f"Unknown topic encountered: '{raw_topic}'. "
                           f"Please add this to the topic_mapping in config/mappings.json "
                           f"or run with --dump-categories-only to collect all categories first.")
        
        self.logger.warning(f"Unknown topic: {raw_topic}, defaulting to General")
        return "General"

    async def _random_delay(self) -> None:
        """Add a random delay between requests to appear more human-like."""
        delay = random.uniform(RATE_LIMITS['random_delay_min'], RATE_LIMITS['random_delay_max'])
        await asyncio.sleep(delay)

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(USER_AGENTS)

    async def _extract_descriptions_from_results(self, page: Page, questions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Submit the quiz and extract descriptions/explanations from the results page."""
        try:
            # First, check if there's a submit button or if answers need to be selected
            submit_button = await page.query_selector('input[type="submit"], button[type="submit"], button:has-text("Submit"), input[value*="Submit"]')
            
            if not submit_button:
                self.logger.warning("No submit button found, trying to find other submission methods")
                # Try to find any button that might submit the quiz
                submit_button = await page.query_selector('button, input[type="button"]')
            
            if submit_button:
                # Select random answers for all questions to submit the quiz
                await self._select_quiz_answers(page, questions)
                
                # Submit the quiz
                self.logger.debug("Submitting quiz to get results page")
                await submit_button.click()
                
                # Wait for results page to load
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                # Extract descriptions from results page
                descriptions = await self._extract_descriptions_from_page(page, questions)
                
                self.logger.info(f"Extracted {len(descriptions)} question descriptions from results page")
                return descriptions
            else:
                self.logger.warning("Could not find submit button, skipping description extraction")
                return {}
                
        except Exception as e:
            self.logger.warning(f"Error extracting descriptions from results: {e}")
            return {}

    async def _select_quiz_answers(self, page: Page, questions: List[Dict[str, Any]]) -> None:
        """Select random answers for all questions to enable quiz submission."""
        try:
            for question in questions:
                question_number = question.get('questionNumber')
                if question_number:
                    # Find radio buttons for this question
                    radio_buttons = await page.query_selector_all(f'input[name="q{question_number}"]')
                    if radio_buttons:
                        # Select the first option (we don't care about correctness, just need to submit)
                        await radio_buttons[0].click()
                        self.logger.debug(f"Selected answer for question {question_number}")
                        
        except Exception as e:
            self.logger.warning(f"Error selecting quiz answers: {e}")

    async def _extract_descriptions_from_page(self, page: Page, questions: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract descriptions/explanations from the current results page."""
        try:
            descriptions = await page.evaluate("""
                (questions) => {
                    const descriptions = {};
                    
                    // Strategy 1: Look for question-specific explanation sections
                    const explanationSelectors = [
                        '.question-explanation',
                        '.question-summary', 
                        '.explanation',
                        '.answer-explanation',
                        '.question-info',
                        '.trivia-fact',
                        '.additional-info'
                    ];
                    
                    // Try each selector
                    for (const selector of explanationSelectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            elements.forEach((el, index) => {
                                const text = el.textContent.trim();
                                if (text.length > 10) {
                                    descriptions[String(index + 1)] = text;
                                }
                            });
                            if (Object.keys(descriptions).length > 0) {
                                return descriptions;
                            }
                        }
                    }
                    
                    // Strategy 2: Look for numbered explanations that match question numbers
                    questions.forEach(question => {
                        const qNum = question.questionNumber;
                        
                        // Look for explanations that start with question number
                        const textNodes = document.evaluate(
                            `//text()[contains(., "${qNum}.") or contains(., "Question ${qNum}")]`,
                            document,
                            null,
                            XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE,
                            null
                        );
                        
                        for (let i = 0; i < textNodes.snapshotLength; i++) {
                            const node = textNodes.snapshotItem(i);
                            const parent = node.parentElement;
                            if (parent) {
                                const text = parent.textContent.trim();
                                // Look for explanation patterns
                                const explanationMatch = text.match(new RegExp(`${qNum}[.:]?\\s*(.{20,})`, 'i'));
                                if (explanationMatch && explanationMatch[1]) {
                                    descriptions[qNum] = explanationMatch[1].trim();
                                }
                            }
                        }
                    });
                    
                    // Strategy 3: Look for any informational text blocks
                    if (Object.keys(descriptions).length === 0) {
                        const infoElements = document.querySelectorAll('p, div, span');
                        let explanationTexts = [];
                        
                        infoElements.forEach(el => {
                            const text = el.textContent.trim();
                            // Filter out short texts and common UI elements
                            if (text.length > 30 && 
                                !text.toLowerCase().includes('score') &&
                                !text.toLowerCase().includes('back to') &&
                                !text.toLowerCase().includes('next quiz') &&
                                !text.toLowerCase().includes('copyright') &&
                                el.children.length === 0) { // Text-only elements
                                explanationTexts.push(text);
                            }
                        });
                        
                        // Assign explanations to questions based on order
                        explanationTexts.slice(0, questions.length).forEach((text, index) => {
                            descriptions[String(index + 1)] = text;
                        });
                    }
                    
                    return descriptions;
                }
            """, questions)
            
            return descriptions
            
        except Exception as e:
            self.logger.error(f"Error extracting descriptions from page: {e}")
            return {}

    async def _extract_all_questions_from_page(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all questions from a single page (FunTrivia's format)."""
        try:
            # Extract all questions and their options using the actual FunTrivia structure
            questions_data = await page.evaluate("""
                () => {
                    const questions = [];
                    
                    // Find all question elements (numbered questions in bold)
                    const questionElements = Array.from(document.querySelectorAll('b')).filter(b => {
                        const text = b.textContent.trim();
                        return /^\d+\.\s/.test(text); // Starts with number and dot
                    });
                    
                    questionElements.forEach((questionEl, index) => {
                        const questionText = questionEl.textContent.trim();
                        const questionNumber = questionText.match(/^(\d+)\./)?.[1];
                        
                        if (!questionNumber) return;
                        
                        // Find radio buttons for this question
                        const radioButtons = Array.from(document.querySelectorAll(`input[name="q${questionNumber}"]`));
                        const options = radioButtons.map(radio => radio.value).filter(value => value && value.trim());
                        
                        if (questionText && options.length >= 2) {
                            // Clean up question text (remove number prefix)
                            const cleanQuestion = questionText.replace(/^\d+\.\s*/, '').trim();
                            
                            questions.push({
                                question: cleanQuestion,
                                options: options,
                                questionNumber: questionNumber
                            });
                        }
                    });
                    
                    return questions;
                }
            """)
            
            self.logger.info(f"Extracted {len(questions_data)} questions from page")
            return questions_data
            
        except Exception as e:
            self.logger.error(f"Error extracting questions from page: {e}")
            return []

    async def _extract_questions_alternative(self, page: Page) -> List[Dict[str, Any]]:
        """Alternative question extraction method for pages that don't match the standard format."""
        try:
            questions_data = await page.evaluate("""
                () => {
                    const questions = [];
                    
                    // Alternative strategy 1: Look for any numbered text that might be questions
                    const allText = document.body.innerText;
                    const lines = allText.split('\\n').map(line => line.trim()).filter(line => line);
                    
                    let currentQuestion = null;
                    let options = [];
                    
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];
                        
                        // Check if this line looks like a question (starts with number)
                        const questionMatch = line.match(/^(\\d+)\\.?\\s*(.+)/);
                        if (questionMatch && questionMatch[2].length > 10) {
                            // Save previous question if we have one
                            if (currentQuestion && options.length >= 2) {
                                questions.push({
                                    question: currentQuestion,
                                    options: options,
                                    questionNumber: questions.length + 1
                                });
                            }
                            
                            currentQuestion = questionMatch[2].trim();
                            options = [];
                        }
                        // Check if this line looks like an option (a), b), etc.)
                        else if (line.match(/^[a-d]\\)?\\s*.+/i) && currentQuestion) {
                            const optionText = line.replace(/^[a-d]\\)?\\s*/i, '').trim();
                            if (optionText.length > 0) {
                                options.push(optionText);
                            }
                        }
                    }
                    
                    // Don't forget the last question
                    if (currentQuestion && options.length >= 2) {
                        questions.push({
                            question: currentQuestion,
                            options: options,
                            questionNumber: questions.length + 1
                        });
                    }
                    
                    return questions;
                }
            """)
            
            self.logger.info(f"Alternative extraction found {len(questions_data)} questions")
            return questions_data
            
        except Exception as e:
            self.logger.error(f"Error in alternative question extraction: {e}")
            return [] 