#!/usr/bin/env python3
"""
Batch Category Scraper for FunTrivia

This script divides categories into optimal batches and runs multiple scraper instances.
Automatically distributes categories for maximum efficiency and minimal risk.

Usage:
    python tools/batch_scraper.py --batch-size 6 --parallel-jobs 4 --questions-per-batch 10000
    python tools/batch_scraper.py --mode aggressive --auto-balance
    python tools/batch_scraper.py --resume-from-batch 5
"""

import json
import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ProcessPoolExecutor
import os

class CategoryBatchManager:
    """Manages category batching and parallel scraping."""
    
    def __init__(self, categories_file: str = "output/all_categories.json"):
        self.categories_file = Path(categories_file)
        self.categories_data = {}
        self.category_urls = []
        self.load_categories()
    
    def load_categories(self):
        """Load categories from saved JSON file."""
        if not self.categories_file.exists():
            print(f"❌ Categories file not found: {self.categories_file}")
            print("Run: python src/main.py --dump-categories-only first")
            sys.exit(1)
        
        with open(self.categories_file, 'r') as f:
            self.categories_data = json.load(f)
        
        # Extract category URLs
        url_patterns = self.categories_data.get('url_patterns', {})
        category_info = url_patterns.get('categories', [])
        
        self.category_urls = []
        for info in category_info:
            if isinstance(info, dict) and 'url' in info:
                self.category_urls.append(info['url'])
        
        if not self.category_urls:
            print(f"❌ No category URLs found in {self.categories_file}")
            sys.exit(1)
        
        print(f"✅ Loaded {len(self.category_urls)} categories")
    
    def analyze_categories(self) -> Dict[str, Any]:
        """Analyze categories to create optimal batches."""
        analysis = {
            'total_categories': len(self.category_urls),
            'domain_distribution': {},
            'estimated_questions': {},
            'priority_categories': [],
            'recommended_batches': 0
        }
        
        # Analyze domains
        domains = self.categories_data.get('raw_domains', {})
        analysis['domain_distribution'] = dict(sorted(domains.items(), key=lambda x: x[1], reverse=True))
        
        # Estimate questions per category based on historical data
        for url in self.category_urls:
            category_name = url.split('/')[-1].replace('.html', '')
            # Rough estimation based on domain popularity
            if 'entertainment' in url.lower() or 'movies' in url.lower():
                estimated = 500-2000
            elif 'music' in url.lower() or 'sports' in url.lower():
                estimated = 300-1500
            elif 'history' in url.lower() or 'geography' in url.lower():
                estimated = 200-1000
            else:
                estimated = 100-500
            
            analysis['estimated_questions'][url] = estimated
        
        # Create priority list
        priority_keywords = ['entertainment', 'movies', 'music', 'sports', 'history', 'science']
        for keyword in priority_keywords:
            matching = [url for url in self.category_urls if keyword in url.lower()]
            analysis['priority_categories'].extend(matching[:5])  # Top 5 per keyword
        
        # Remove duplicates
        analysis['priority_categories'] = list(set(analysis['priority_categories']))
        
        # Recommend batch size
        total_cats = len(self.category_urls)
        if total_cats > 80:
            analysis['recommended_batches'] = 8-12
        elif total_cats > 40:
            analysis['recommended_batches'] = 6-8
        else:
            analysis['recommended_batches'] = 4-6
        
        return analysis
    
    def create_batches(self, batch_size: int = 6, strategy: str = "balanced") -> List[List[str]]:
        """Create optimized batches of categories."""
        analysis = self.analyze_categories()
        
        if strategy == "priority":
            # Start with high-priority categories
            categories = analysis['priority_categories'] + [
                url for url in self.category_urls 
                if url not in analysis['priority_categories']
            ]
        elif strategy == "balanced":
            # Mix high and low traffic categories
            high_traffic = analysis['priority_categories']
            other_cats = [url for url in self.category_urls if url not in high_traffic]
            
            categories = []
            for i in range(max(len(high_traffic), len(other_cats))):
                if i < len(high_traffic):
                    categories.append(high_traffic[i])
                if i < len(other_cats):
                    categories.append(other_cats[i])
        else:
            # Simple sequential
            categories = self.category_urls
        
        # Split into batches
        batches = []
        for i in range(0, len(categories), batch_size):
            batch = categories[i:i + batch_size]
            batches.append(batch)
        
        return batches
    
    def format_categories_for_cli(self, category_urls: List[str]) -> str:
        """Convert category URLs to CLI-friendly format."""
        # Extract just the category names
        category_names = []
        for url in category_urls:
            # Extract meaningful part from URL
            parts = url.replace('https://www.funtrivia.com/quizzes/', '').split('/')
            if len(parts) >= 2:
                category_names.append(parts[0])  # Use domain as category
            else:
                category_names.append(parts[0])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in category_names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)
        
        return ','.join(unique_names[:6])  # Limit to 6 for CLI
    
    def run_batch(self, batch_categories: List[str], batch_num: int, **kwargs) -> Dict[str, Any]:
        """Run scraper for a single batch."""
        print(f"\n🚀 Starting Batch {batch_num}")
        print(f"📁 Categories: {len(batch_categories)}")
        
        # Format categories for command line
        categories_str = self.format_categories_for_cli(batch_categories)
        
        # Build command
        cmd = [
            "python3", "src/main.py",
            "--categories", categories_str,
            "--speed-profile", kwargs.get('speed_profile', 'fast'),
            "--max-questions", str(kwargs.get('max_questions', 5000)),
            "--concurrency", str(kwargs.get('concurrency', 6))
        ]
        
        if kwargs.get('backup', True):
            cmd.append("--backup")
        
        print(f"🔧 Command: {' '.join(cmd)}")
        
        # Run the command
        start_time = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=kwargs.get('timeout', 3600))
            
            elapsed = time.time() - start_time
            
            batch_result = {
                'batch_num': batch_num,
                'categories': batch_categories,
                'elapsed_time': elapsed,
                'return_code': result.returncode,
                'stdout_lines': len(result.stdout.split('\n')),
                'stderr_lines': len(result.stderr.split('\n')),
                'success': result.returncode == 0
            }
            
            if result.returncode == 0:
                print(f"✅ Batch {batch_num} completed successfully in {elapsed:.1f}s")
            else:
                print(f"❌ Batch {batch_num} failed with code {result.returncode}")
                print(f"Error output: {result.stderr[:200]}...")
            
            return batch_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ Batch {batch_num} timed out after {kwargs.get('timeout', 3600)}s")
            return {
                'batch_num': batch_num,
                'categories': batch_categories,
                'elapsed_time': kwargs.get('timeout', 3600),
                'return_code': -1,
                'success': False,
                'error': 'timeout'
            }
        except Exception as e:
            print(f"💥 Batch {batch_num} crashed: {e}")
            return {
                'batch_num': batch_num,
                'categories': batch_categories,
                'elapsed_time': time.time() - start_time,
                'return_code': -2,
                'success': False,
                'error': str(e)
            }
    
    def run_parallel_batches(self, batches: List[List[str]], max_workers: int = 4, **kwargs):
        """Run multiple batches in parallel."""
        print(f"\n🔄 Starting parallel execution of {len(batches)} batches")
        print(f"👥 Max parallel jobs: {max_workers}")
        print("=" * 60)
        
        results = []
        
        # Use ThreadPoolExecutor for I/O bound subprocess calls
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batches
            future_to_batch = {
                executor.submit(self.run_batch, batch, i+1, **kwargs): i+1 
                for i, batch in enumerate(batches)
            }
            
            # Collect results as they complete
            for future in future_to_batch:
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Print progress
                    completed = len(results)
                    total = len(batches)
                    print(f"📊 Progress: {completed}/{total} batches completed")
                    
                except Exception as e:
                    batch_num = future_to_batch[future]
                    print(f"💥 Batch {batch_num} failed with exception: {e}")
                    results.append({
                        'batch_num': batch_num,
                        'success': False,
                        'error': str(e)
                    })
        
        # Summary
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        total_time = sum(r.get('elapsed_time', 0) for r in results)
        
        print("\n" + "=" * 60)
        print("📊 BATCH PROCESSING SUMMARY")
        print("=" * 60)
        print(f"✅ Successful batches: {successful}/{len(results)}")
        print(f"❌ Failed batches: {failed}")
        print(f"⏱️  Total processing time: {total_time:.1f}s")
        print(f"⚡ Average per batch: {total_time/len(results):.1f}s")
        
        return results
    
    def print_analysis(self):
        """Print category analysis."""
        analysis = self.analyze_categories()
        
        print("\n📊 CATEGORY ANALYSIS")
        print("=" * 50)
        print(f"Total categories: {analysis['total_categories']}")
        print(f"Recommended batches: {analysis['recommended_batches']}")
        
        print(f"\n🏆 Top Domains by Quiz Count:")
        for domain, count in list(analysis['domain_distribution'].items())[:10]:
            print(f"  {domain}: {count} quizzes")
        
        print(f"\n⭐ Priority Categories ({len(analysis['priority_categories'])}):")
        for i, url in enumerate(analysis['priority_categories'][:10], 1):
            category = url.split('/')[-2] if '/' in url else url
            print(f"  {i}. {category}")
        
        if len(analysis['priority_categories']) > 10:
            print(f"  ... and {len(analysis['priority_categories']) - 10} more")

def main():
    parser = argparse.ArgumentParser(description="FunTrivia Batch Category Scraper")
    parser.add_argument('--batch-size', type=int, default=6, help='Categories per batch (default: 6)')
    parser.add_argument('--parallel-jobs', type=int, default=4, help='Parallel batch jobs (default: 4)')
    parser.add_argument('--questions-per-batch', type=int, default=5000, help='Max questions per batch (default: 5000)')
    parser.add_argument('--speed-profile', choices=['normal', 'fast', 'aggressive', 'turbo'], 
                       default='fast', help='Speed profile (default: fast)')
    parser.add_argument('--strategy', choices=['balanced', 'priority', 'sequential'], 
                       default='balanced', help='Batch creation strategy (default: balanced)')
    parser.add_argument('--categories-file', default='output/all_categories.json', 
                       help='Categories JSON file (default: output/all_categories.json)')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze categories, don\'t run scraper')
    parser.add_argument('--resume-from-batch', type=int, help='Resume from specific batch number')
    parser.add_argument('--timeout', type=int, default=3600, help='Timeout per batch in seconds (default: 3600)')
    parser.add_argument('--no-backup', action='store_true', help='Disable backup creation')
    
    args = parser.parse_args()
    
    # Initialize manager
    manager = CategoryBatchManager(args.categories_file)
    
    # Show analysis
    manager.print_analysis()
    
    if args.analyze_only:
        return
    
    # Create batches
    print(f"\n🔨 Creating batches with strategy: {args.strategy}")
    batches = manager.create_batches(args.batch_size, args.strategy)
    
    # Resume from specific batch if requested
    if args.resume_from_batch:
        if args.resume_from_batch > len(batches):
            print(f"❌ Resume batch {args.resume_from_batch} > total batches {len(batches)}")
            return
        batches = batches[args.resume_from_batch - 1:]
        print(f"📍 Resuming from batch {args.resume_from_batch}")
    
    print(f"📦 Created {len(batches)} batches of ~{args.batch_size} categories each")
    
    # Prepare kwargs for batch execution
    batch_kwargs = {
        'speed_profile': args.speed_profile,
        'max_questions': args.questions_per_batch,
        'concurrency': 6,  # Fixed for stability
        'timeout': args.timeout,
        'backup': not args.no_backup
    }
    
    # Run batches
    results = manager.run_parallel_batches(batches, args.parallel_jobs, **batch_kwargs)
    
    # Save results
    results_file = f"batch_results_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {results_file}")

if __name__ == "__main__":
    main() 