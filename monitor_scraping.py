#!/usr/bin/env python3
"""
Monitor scraping progress and check for duplicates in real-time.
"""

import pandas as pd
import time
import os
from datetime import datetime

def monitor_progress():
    """Monitor the scraping progress and check for duplicates."""
    
    print("🔍 Monitoring Scraping Progress...")
    print("=" * 50)
    
    start_time = datetime.now()
    initial_count = 0
    
    # Get initial count
    if os.path.exists('output/multiple_choice.csv'):
        df = pd.read_csv('output/multiple_choice.csv')
        initial_count = len(df)
        print(f"📊 Starting count: {initial_count} questions")
    
    print(f"⏰ Started monitoring at: {start_time.strftime('%H:%M:%S')}")
    print("\nPress Ctrl+C to stop monitoring\n")
    
    try:
        while True:
            if os.path.exists('output/multiple_choice.csv'):
                df = pd.read_csv('output/multiple_choice.csv')
                current_count = len(df)
                new_questions = current_count - initial_count
                
                # Check for duplicates
                duplicates = df[df.duplicated(subset=['Question'], keep=False)]
                duplicate_count = len(duplicates)
                
                # Calculate rate
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                rate = new_questions / elapsed if elapsed > 0 else 0
                
                # Status update
                status = "✅ CLEAN" if duplicate_count == 0 else f"⚠️ {duplicate_count} DUPLICATES"
                
                print(f"📊 {datetime.now().strftime('%H:%M:%S')} | "
                      f"Total: {current_count} (+{new_questions}) | "
                      f"Rate: {rate:.1f}/min | "
                      f"Status: {status}")
                
                if duplicate_count > 0:
                    print(f"   🚨 DUPLICATES DETECTED: {duplicate_count} duplicate entries found!")
                    # Show some examples
                    unique_duplicates = duplicates['Question'].nunique()
                    print(f"   📋 {unique_duplicates} unique questions are duplicated")
                
            else:
                print(f"📊 {datetime.now().strftime('%H:%M:%S')} | Waiting for CSV file to be created...")
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print(f"\n🛑 Monitoring stopped at {datetime.now().strftime('%H:%M:%S')}")
        
        # Final summary
        if os.path.exists('output/multiple_choice.csv'):
            df = pd.read_csv('output/multiple_choice.csv')
            final_count = len(df)
            total_new = final_count - initial_count
            
            duplicates = df[df.duplicated(subset=['Question'], keep=False)]
            duplicate_count = len(duplicates)
            
            print(f"\n📈 FINAL SUMMARY:")
            print(f"   Initial: {initial_count} questions")
            print(f"   Final: {final_count} questions")
            print(f"   Added: {total_new} questions")
            
            if duplicate_count == 0:
                print(f"   ✅ NO DUPLICATES - Fix working perfectly!")
            else:
                print(f"   ⚠️ {duplicate_count} duplicates found - needs investigation")

if __name__ == "__main__":
    monitor_progress() 