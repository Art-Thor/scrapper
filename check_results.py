#!/usr/bin/env python3
"""Check the results of the re-scraping to see description improvements."""

import pandas as pd

def check_results():
    """Check the latest Roman quiz questions for description improvements."""
    
    df = pd.read_csv('output/multiple_choice.csv')
    
    # Find the latest questions (likely the re-scraped ones)
    latest_questions = df.tail(30)  # Last 30 questions
    
    print("🔍 Latest Questions Analysis:")
    print("=" * 50)
    
    with_desc = 0
    without_desc = 0
    
    for _, row in latest_questions.iterrows():
        key = row['Key']
        description = row['Description']
        question = str(row['Question'])[:50] + "..."
        
        if pd.notna(description) and str(description) != 'nan' and len(str(description)) > 5:
            desc_len = len(str(description))
            with_desc += 1
            print(f"✅ {key}: {desc_len} chars")
            print(f"   Q: {question}")
            print(f"   D: {str(description)[:100]}...")
            print()
        else:
            without_desc += 1
            print(f"❌ {key}: NO DESCRIPTION")
            print(f"   Q: {question}")
            print()
    
    print("📊 SUMMARY:")
    print(f"Questions WITH descriptions: {with_desc}")
    print(f"Questions WITHOUT descriptions: {without_desc}")
    print(f"Success rate: {(with_desc/(with_desc+without_desc)*100):.1f}%")
    
    # Also check overall improvement
    print("\n📈 OVERALL IMPROVEMENT:")
    total_questions = len(df)
    total_with_desc = len(df[df['Description'].notna() & (df['Description'] != '') & (df['Description'] != 'EMPTY') & (df['Description'] != 'nan')])
    total_without_desc = total_questions - total_with_desc
    
    print(f"Total questions in CSV: {total_questions}")
    print(f"Total WITH descriptions: {total_with_desc}")  
    print(f"Total WITHOUT descriptions: {total_without_desc}")
    print(f"Overall success rate: {(total_with_desc/total_questions*100):.1f}%")

if __name__ == "__main__":
    check_results() 