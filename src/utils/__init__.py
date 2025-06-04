"""
Utility modules for the FunTrivia scraper.

This package contains utility classes and functions for:
- Rate limiting requests
- Google Sheets integration with enhanced error handling
- CSV handling with append/overwrite capabilities and validation
- Persistent question indexing
- Data processing and validation
- Performance monitoring and metrics collection
- Compliance checking and ethical scraping practices
"""

from .rate_limiter import RateLimiter
from .sheets import GoogleSheetsUploader, test_google_sheets_setup
from .csv_handler import CSVHandler
from .indexing import QuestionIndexer
from .validation import (
    DataValidator, 
    CSVTemplateValidator, 
    validate_scraped_data, 
    print_validation_report,
    validate_csv_files
)
from .monitoring import (
    ScrapingMetrics, 
    HealthMonitor, 
    generate_performance_report,
    create_monitoring_dashboard
)
from .compliance import (
    RobotsChecker, 
    EthicalScraper, 
    TermsOfServiceChecker,
    run_compliance_check,
    create_compliance_config,
    save_compliance_report
)

__all__ = [
    # Core utilities
    'RateLimiter', 
    'GoogleSheetsUploader', 
    'CSVHandler', 
    'QuestionIndexer',
    
    # Validation
    'DataValidator',
    'CSVTemplateValidator', 
    'validate_scraped_data',
    'print_validation_report',
    'validate_csv_files',
    
    # Monitoring
    'ScrapingMetrics',
    'HealthMonitor',
    'generate_performance_report',
    'create_monitoring_dashboard',
    
    # Compliance
    'RobotsChecker',
    'EthicalScraper', 
    'TermsOfServiceChecker',
    'run_compliance_check',
    'create_compliance_config',
    'save_compliance_report',
    
    # Testing functions
    'test_google_sheets_setup'
] 