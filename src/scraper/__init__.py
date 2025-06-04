"""
Scraper modules for different quiz platforms.

This package contains scraper implementations for various quiz websites:
- BaseScraper: Abstract base class for all scrapers
- FunTriviaScraper: FunTrivia.com specific implementation
"""

from .base import BaseScraper
from .funtrivia import FunTriviaScraper

__all__ = ['BaseScraper', 'FunTriviaScraper'] 