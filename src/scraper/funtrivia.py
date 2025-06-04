import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import re
import logging
import random
import sys
import os
from playwright.async_api import Browser, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Add the src directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from .base import BaseScraper
from utils.rate_limiter import RateLimiter
from utils.indexing import QuestionIndexer

class FunTriviaScraper(BaseScraper):
    def __init__(self, config_path: str = "config/settings.json"):
        super().__init__(config_path)
        self.mappings = self._load_mappings()
        self.indexer = QuestionIndexer()
        self.rate_limiter = RateLimiter(
            self.config['scraper']['rate_limit']['requests_per_minute']
        )

    def _load_mappings(self) -> Dict[str, Any]:
        """Load mappings from JSON file."""
        try:
            with open("config/mappings.json", 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load mappings: {e}")
            raise

    async def initialize(self) -> None:
        """Initialize the scraper with a browser instance."""
        try:
            from playwright.async_api import async_playwright
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
            
            # Create a semaphore to limit concurrent scraping
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

            # Scrape categories concurrently
            tasks = [scrape_category(category) for category in categories]
            results = await asyncio.gather(*tasks)
            
            # Flatten results
            for category_questions in results:
                questions.extend(category_questions)
                if max_questions and len(questions) >= max_questions:
                    questions = questions[:max_questions]
                    break

            self.logger.info(f"Successfully scraped {len(questions)} questions")
            return questions
        except Exception as e:
            self.logger.error(f"Error during question scraping: {e}")
            raise

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
                await page.goto(f"{self.config['scraper']['base_url']}/quizzes/", timeout=self.config['scraper']['timeouts']['page_load'])
                await page.wait_for_load_state('networkidle', timeout=self.config['scraper']['timeouts']['network_idle'])
                
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
                await page.goto(category_url, timeout=self.config['scraper']['timeouts']['page_load'])
                await page.wait_for_load_state('networkidle', timeout=self.config['scraper']['timeouts']['network_idle'])
                
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
        """Scrape all questions from a quiz - Updated for FunTrivia's single-page format."""
        context = await self.browser.new_context(
            user_agent=self._get_random_user_agent()
        )
        page = await context.new_page()
        
        try:
            async with self.rate_limiter:
                await page.goto(quiz_url, timeout=self.config['scraper']['timeouts']['quiz_page'])
                await page.wait_for_load_state('networkidle', timeout=self.config['scraper']['timeouts']['quiz_wait'])
                
                # Get quiz metadata
                difficulty = await self._get_quiz_difficulty(page)
                domain = await self._get_quiz_domain(page)
                topic = await self._get_quiz_topic(page)
                
                # Extract all questions from the single page
                questions = await self._extract_all_questions_from_page(page)
                
                if not questions:
                    self.logger.warning(f"No questions found using primary extraction method")
                    # Try alternative extraction methods
                    questions = await self._extract_questions_alternative(page)
                    
                if not questions:
                    self.logger.warning(f"No questions found on quiz page: {quiz_url}")
                    return []
                
                # Process each question
                processed_questions = []
                for i, question_data in enumerate(questions):
                    if not question_data:
                        continue
                    
                    # Generate unique question ID using the indexer
                    question_id = self.indexer.get_next_id(question_data['type'])
                    
                    # Update question data with all metadata
                    question_data.update({
                        "id": question_id,
                        "difficulty": self.map_difficulty(difficulty),
                        "domain": self.map_domain(domain),
                        "topic": self.map_topic(topic),
                        "correct_answer": question_data.get('correct_answer', question_data['options'][0] if question_data['options'] else ''),
                        "hint": question_data.get('hint', '')
                    })
                    
                    processed_questions.append(question_data)
                    self.logger.debug(f"Processed question {i+1}: {question_data['question'][:50]}...")
                
                self.logger.info(f"Successfully extracted {len(processed_questions)} questions from {quiz_url}")
                return processed_questions
                
        except PlaywrightTimeoutError:
            self.logger.warning(f"Timeout while scraping quiz: {quiz_url}")
            return []
        except Exception as e:
            self.logger.error(f"Error scraping quiz {quiz_url}: {e}")
            return []
        finally:
            await context.close()

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
                            
                            // Determine question type
                            let questionType = "multiple_choice";
                            if (options.length === 2 && 
                                options.every(opt => ['true', 'false', 'yes', 'no'].includes(opt.toLowerCase()))) {
                                questionType = "true_false";
                            }
                            
                            questions.push({
                                type: questionType,
                                question: cleanQuestion,
                                options: options,
                                questionNumber: questionNumber
                            });
                        }
                    });
                    
                    return questions;
                }
            """)
            
            if not questions_data:
                self.logger.warning("No questions found using primary extraction method")
                return []
            
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
                                    type: options.length === 2 && 
                                          options.every(opt => ['true', 'false', 'yes', 'no'].includes(opt.toLowerCase())) 
                                          ? "true_false" : "multiple_choice",
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
                            type: options.length === 2 && 
                                  options.every(opt => ['true', 'false', 'yes', 'no'].includes(opt.toLowerCase())) 
                                  ? "true_false" : "multiple_choice",
                            question: currentQuestion,
                            options: options,
                            questionNumber: questions.length + 1
                        });
                    }
                    
                    return questions;
                }
            """)
            
            if questions_data and len(questions_data) > 0:
                self.logger.info(f"Alternative extraction found {len(questions_data)} questions")
                return questions_data
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error in alternative question extraction: {e}")
            return []

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
        import aiohttp
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
        self.logger.warning(f"Unknown difficulty level: {raw_difficulty}, defaulting to Normal")
        return "Normal"

    def map_domain(self, raw_domain: str) -> str:
        """Map FunTrivia domain to standardized value."""
        for std_domain, raw_values in self.mappings['domain_mapping'].items():
            if raw_domain.lower() in [v.lower() for v in raw_values]:
                return std_domain
        self.logger.warning(f"Unknown domain: {raw_domain}, defaulting to Culture")
        return "Culture"

    def map_topic(self, raw_topic: str) -> str:
        """Map FunTrivia topic to standardized value."""
        for std_topic, raw_values in self.mappings['topic_mapping'].items():
            if raw_topic.lower() in [v.lower() for v in raw_values]:
                return std_topic
        self.logger.warning(f"Unknown topic: {raw_topic}, defaulting to General")
        return "General"

    async def _random_delay(self) -> None:
        """Add a random delay between requests to appear more human-like."""
        delay = random.uniform(1, 3)
        await asyncio.sleep(delay)

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.config['scraper']['user_agents']) 