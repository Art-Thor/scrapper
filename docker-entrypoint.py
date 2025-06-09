#!/usr/bin/env python3
"""
Docker entrypoint script for FunTrivia Scraper
Supports different operation modes: batch, single, monitor
"""

import argparse
import sys
import subprocess
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='FunTrivia Scraper Docker Entry Point')
    
    # Operation modes
    parser.add_argument('--mode', choices=['batch', 'single', 'monitor', 'health'], 
                       default='batch', help='Container operation mode')
    
    # Batch mode parameters
    parser.add_argument('--batch-size', type=int, default=2, 
                       help='Number of categories per batch')
    parser.add_argument('--parallel-jobs', type=int, default=1,
                       help='Number of parallel batches')
    parser.add_argument('--questions-per-batch', type=int, default=50,
                       help='Maximum questions per batch')
    parser.add_argument('--speed-profile', choices=['normal', 'fast', 'aggressive'], 
                       default='normal', help='Speed profile')
    parser.add_argument('--strategy', choices=['balanced', 'priority', 'sequential'],
                       default='priority', help='Batch creation strategy')
    
    # Single mode parameters
    parser.add_argument('--max-questions', type=int, default=100,
                       help='Maximum questions for single mode')
    parser.add_argument('--categories', type=str, 
                       help='Comma-separated categories for single mode')
    
    # Common parameters
    parser.add_argument('--timeout', type=int, default=7200,
                       help='Execution timeout in seconds')
    parser.add_argument('--resume-from-batch', type=int,
                       help='Resume from specified batch number')
    
    args = parser.parse_args()
    
    # Проверка необходимых директорий
    ensure_directories()
    
    if args.mode == 'health':
        health_check()
        return
    
    elif args.mode == 'monitor':
        monitor_mode()
        return
        
    elif args.mode == 'batch':
        run_batch_mode(args)
        
    elif args.mode == 'single':
        run_single_mode(args)

def ensure_directories():
    """Create necessary directories"""
    dirs = ['output', 'assets/images', 'assets/audio', 'logs', 'credentials']
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Check if all_categories.json exists
    if not Path('output/all_categories.json').exists():
        print("⚠️  File output/all_categories.json not found!")
        print("💡 Starting category collection...")
        try:
            subprocess.run([
                'python', 'src/main.py', 
                '--dump-categories-only'
            ], check=True, timeout=600)
            print("✅ Categories collected successfully")
        except subprocess.TimeoutExpired:
            print("❌ Timeout during category collection")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during category collection: {e}")
            sys.exit(1)

def health_check():
    """Container health check"""
    try:
        # Check Python imports
        import src.main
        
        # Check Playwright
        import playwright.async_api
        
        # Check configuration
        config_file = Path('config/settings.json')
        if not config_file.exists():
            print("❌ Configuration file not found")
            sys.exit(1)
        
        # Check directories
        for dir_path in ['output', 'logs', 'assets']:
            if not Path(dir_path).exists():
                print(f"❌ Directory {dir_path} not found")
                sys.exit(1)
        
        print("✅ Container healthy")
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Health check error: {e}")
        sys.exit(1)

def monitor_mode():
    """Monitor mode - shows logs and metrics"""
    print("📊 FunTrivia Scraper Monitor Mode")
    print("=" * 50)
    
    # Show current metrics
    try:
        import json
        with open('scraping_metrics.json', 'r') as f:
            metrics = json.load(f)
            
        if metrics:
            latest = metrics[-1]
            print(f"📈 Latest session: {latest.get('session_id', 'unknown')}")
            print(f"⏱️  Duration: {latest.get('duration_seconds', 0):.0f} sec")
            print(f"❓ Questions: {latest.get('questions_scraped', 0)}")
            print(f"⚡ Speed: {latest.get('performance', {}).get('avg_questions_per_minute', 0):.1f} q/min")
    except:
        print("📊 No metrics found")
    
    print("\n📋 Log monitoring (Ctrl+C to exit):")
    try:
        subprocess.run(['tail', '-f', 'logs/scraper.log'])
    except KeyboardInterrupt:
        print("\n👋 Monitoring finished")

def run_batch_mode(args):
    """Run in batch mode"""
    print("🚀 Starting FunTrivia Scraper in batch mode")
    print("=" * 50)
    print(f"📦 Batch size: {args.batch_size}")
    print(f"⚡ Parallel jobs: {args.parallel_jobs}")
    print(f"❓ Questions per batch: {args.questions_per_batch}")
    print(f"🏃 Speed profile: {args.speed_profile}")
    print(f"📋 Strategy: {args.strategy}")
    print("=" * 50)
    
    cmd = [
        'python', 'tools/batch_scraper.py',
        '--batch-size', str(args.batch_size),
        '--parallel-jobs', str(args.parallel_jobs),
        '--questions-per-batch', str(args.questions_per_batch),
        '--speed-profile', args.speed_profile,
        '--strategy', args.strategy,
        '--timeout', str(args.timeout)
    ]
    
    if args.resume_from_batch:
        cmd.extend(['--resume-from-batch', str(args.resume_from_batch)])
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Batch scraping completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during batch scraping: {e}")
        sys.exit(1)

def run_single_mode(args):
    """Run in single mode"""
    print("🎯 Starting FunTrivia Scraper in single mode")
    print("=" * 50)
    print(f"❓ Maximum questions: {args.max_questions}")
    print(f"🏃 Speed profile: {args.speed_profile}")
    if args.categories:
        print(f"📂 Categories: {args.categories}")
    print("=" * 50)
    
    cmd = [
        'python', 'src/main.py',
        '--max-questions', str(args.max_questions),
        '--speed-profile', args.speed_profile
    ]
    
    if args.categories:
        cmd.extend(['--categories', args.categories])
    
    try:
        subprocess.run(cmd, check=True, timeout=args.timeout)
        print("✅ Single scraping completed successfully")
    except subprocess.TimeoutExpired:
        print("⏰ Scraping interrupted by timeout")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during scraping: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 