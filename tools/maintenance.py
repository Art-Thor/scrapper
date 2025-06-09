#!/usr/bin/env python3
"""
Consolidated Maintenance Utilities for FunTrivia Scraper

This script combines various maintenance tasks into a single tool:
- Deduplicate questions
- Clean CSV columns
- Fix missing descriptions
- Analyze duplicates
- Backfill URLs

Usage:
    python tools/maintenance.py --deduplicate
    python tools/maintenance.py --clean-csv
    python tools/maintenance.py --fix-descriptions
    python tools/maintenance.py --analyze-duplicates
    python tools/maintenance.py --all
"""

import argparse
import pandas as pd
import os
import sys
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

class MaintenanceManager:
    """Consolidated maintenance operations for the scraper."""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.csv_files = [
            "multiple_choice.csv",
            "true_false.csv", 
            "sound.csv"
        ]
    
    def create_question_signature(self, row) -> str:
        """Create a unique signature for a question based on text and correct answer."""
        question = str(row.get('Question', '')).strip().lower()
        answer = str(row.get('CorrectAnswer', '')).strip().lower()
        signature = f"{question}|{answer}"
        return hashlib.md5(signature.encode()).hexdigest()
    
    def deduplicate_questions(self) -> Dict[str, int]:
        """Remove duplicate questions from all CSV files."""
        print("🔄 Starting question deduplication...")
        
        total_stats = {
            'original_total': 0,
            'final_total': 0,
            'removed_total': 0
        }
        
        for csv_file in self.csv_files:
            csv_path = self.output_dir / csv_file
            
            if not csv_path.exists():
                print(f"📂 {csv_file} does not exist - skipping")
                continue
            
            # Read CSV
            df = pd.read_csv(csv_path)
            original_count = len(df)
            
            if original_count == 0:
                print(f"📄 {csv_file}: Empty file - skipping")
                continue
            
            print(f"📄 Processing {csv_file}: {original_count} questions")
            
            # Create signatures for deduplication
            df['_signature'] = df.apply(self.create_question_signature, axis=1)
            
            # Find and report duplicates
            duplicates = df[df.duplicated(subset=['_signature'], keep=False)]
            if len(duplicates) > 0:
                print(f"  🔍 Found {len(duplicates)} duplicate entries")
                
                # Show examples
                unique_duplicates = duplicates['_signature'].unique()[:3]
                for sig in unique_duplicates:
                    dup_group = duplicates[duplicates['_signature'] == sig]
                    example = dup_group.iloc[0]
                    print(f"    📋 Duplicate: \"{example['Question'][:60]}...\" ({len(dup_group)} copies)")
            
            # Remove duplicates
            df_deduplicated = df.drop_duplicates(subset=['_signature'], keep='first')
            df_deduplicated = df_deduplicated.drop(columns=['_signature'])
            
            final_count = len(df_deduplicated)
            removed_count = original_count - final_count
            
            if removed_count > 0:
                # Create backup
                backup_path = csv_path.with_suffix('.before_dedup.csv')
                df.drop(columns=['_signature']).to_csv(backup_path, index=False)
                print(f"  💾 Created backup: {backup_path.name}")
                
                # Save deduplicated version
                df_deduplicated.to_csv(csv_path, index=False)
                print(f"  ✅ Removed {removed_count} duplicates")
            else:
                print(f"  ✅ No duplicates found")
            
            total_stats['original_total'] += original_count
            total_stats['final_total'] += final_count
            total_stats['removed_total'] += removed_count
        
        print("\n📊 DEDUPLICATION SUMMARY")
        print("=" * 40)
        print(f"Original questions: {total_stats['original_total']}")
        print(f"Final questions: {total_stats['final_total']}")
        print(f"Duplicates removed: {total_stats['removed_total']}")
        
        if total_stats['removed_total'] > 0:
            percentage = (total_stats['removed_total'] / total_stats['original_total']) * 100
            print(f"Reduction: {percentage:.1f}%")
        
        return total_stats
    
    def clean_csv_columns(self) -> int:
        """Clean up CSV column formatting and content."""
        print("🧹 Starting CSV column cleanup...")
        
        total_cleaned = 0
        
        for csv_file in self.csv_files:
            csv_path = self.output_dir / csv_file
            
            if not csv_path.exists():
                continue
            
            df = pd.read_csv(csv_path)
            print(f"📄 Cleaning {csv_file}: {len(df)} rows")
            
            changes_made = False
            
            # Clean descriptions
            if 'Description' in df.columns:
                cleaned_count = 0
                for idx, desc in enumerate(df['Description']):
                    if pd.isna(desc):
                        continue
                    
                    original_desc = str(desc)
                    cleaned_desc = original_desc
                    
                    # Remove meta information patterns
                    import re
                    cleaned_desc = re.sub(r'Question by player \w+\.?', '', cleaned_desc, flags=re.IGNORECASE)
                    cleaned_desc = re.sub(r'Submitted by \w+\.?', '', cleaned_desc, flags=re.IGNORECASE)
                    cleaned_desc = re.sub(r'Interesting Information:', '', cleaned_desc, flags=re.IGNORECASE)
                    cleaned_desc = re.sub(r'Fun Fact:', '', cleaned_desc, flags=re.IGNORECASE)
                    
                    # Remove extra whitespace
                    cleaned_desc = ' '.join(cleaned_desc.split()).strip()
                    
                    if cleaned_desc != original_desc:
                        df.at[idx, 'Description'] = cleaned_desc
                        cleaned_count += 1
                        changes_made = True
                
                if cleaned_count > 0:
                    print(f"  🧹 Cleaned {cleaned_count} descriptions")
                    total_cleaned += cleaned_count
            
            # Strip whitespace from all text columns
            text_columns = ['Question', 'Option1', 'Option2', 'Option3', 'Option4', 'CorrectAnswer', 'Description']
            for col in text_columns:
                if col in df.columns:
                    original_values = df[col].copy()
                    df[col] = df[col].astype(str).str.strip()
                    if not df[col].equals(original_values):
                        changes_made = True
            
            # Save if changes were made
            if changes_made:
                df.to_csv(csv_path, index=False)
                print(f"  ✅ Saved cleaned {csv_file}")
        
        print(f"\n✅ CSV cleanup completed. Total items cleaned: {total_cleaned}")
        return total_cleaned
    
    def analyze_duplicates(self) -> Dict[str, Any]:
        """Analyze current duplicate patterns."""
        print("🔍 Analyzing duplicate patterns...")
        
        analysis = {
            'duplicate_signatures': set(),
            'duplicate_questions': [],
            'statistics': {}
        }
        
        for csv_file in self.csv_files:
            csv_path = self.output_dir / csv_file
            
            if not csv_path.exists():
                continue
            
            df = pd.read_csv(csv_path)
            print(f"📄 Analyzing {csv_file}: {len(df)} questions")
            
            # Create signatures
            df['_signature'] = df.apply(self.create_question_signature, axis=1)
            
            # Find duplicates
            duplicate_mask = df.duplicated(subset=['_signature'], keep=False)
            duplicates = df[duplicate_mask]
            
            if len(duplicates) > 0:
                print(f"  🔍 Found {len(duplicates)} duplicate entries")
                
                # Group by signature
                for signature in duplicates['_signature'].unique():
                    analysis['duplicate_signatures'].add(signature)
                    dup_group = duplicates[duplicates['_signature'] == signature]
                    
                    analysis['duplicate_questions'].append({
                        'signature': signature,
                        'count': len(dup_group),
                        'question': dup_group.iloc[0]['Question'][:100],
                        'file': csv_file
                    })
            
            analysis['statistics'][csv_file] = {
                'total_questions': len(df),
                'duplicate_entries': len(duplicates),
                'unique_duplicates': len(duplicates['_signature'].unique()) if len(duplicates) > 0 else 0
            }
        
        # Print analysis
        print("\n📊 DUPLICATE ANALYSIS")
        print("=" * 40)
        
        total_duplicates = len(analysis['duplicate_signatures'])
        if total_duplicates > 0:
            print(f"Unique duplicate patterns: {total_duplicates}")
            print("\nTop duplicates:")
            for i, dup in enumerate(sorted(analysis['duplicate_questions'], 
                                         key=lambda x: x['count'], reverse=True)[:5], 1):
                print(f"  {i}. {dup['question']}... ({dup['count']} copies in {dup['file']})")
        else:
            print("✅ No duplicates found!")
        
        return analysis
    
    def fix_missing_descriptions(self) -> int:
        """Attempt to fix missing descriptions by copying from other question types."""
        print("🔧 Fixing missing descriptions...")
        
        # Load all CSV files
        all_questions = {}
        
        for csv_file in self.csv_files:
            csv_path = self.output_dir / csv_file
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                all_questions[csv_file] = df
        
        if not all_questions:
            print("❌ No CSV files found")
            return 0
        
        fixed_count = 0
        
        for csv_file, df in all_questions.items():
            print(f"📄 Processing {csv_file}...")
            
            changes_made = False
            
            for idx, row in df.iterrows():
                if pd.isna(row.get('Description')) or not str(row.get('Description')).strip():
                    question_text = str(row.get('Question', '')).strip()
                    
                    if question_text:
                        # Look for same question in other files
                        for other_file, other_df in all_questions.items():
                            if other_file == csv_file:
                                continue
                            
                            matching_rows = other_df[other_df['Question'].str.contains(
                                question_text[:50], case=False, na=False)]
                            
                            for _, match_row in matching_rows.iterrows():
                                match_desc = match_row.get('Description')
                                if pd.notna(match_desc) and str(match_desc).strip():
                                    df.at[idx, 'Description'] = str(match_desc).strip()
                                    fixed_count += 1
                                    changes_made = True
                                    print(f"  ✅ Fixed description for: {question_text[:50]}...")
                                    break
                            
                            if changes_made:
                                break
            
            # Save changes
            if changes_made:
                csv_path = self.output_dir / csv_file
                df.to_csv(csv_path, index=False)
                print(f"  💾 Saved updated {csv_file}")
        
        print(f"\n✅ Fixed {fixed_count} missing descriptions")
        return fixed_count

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="FunTrivia Scraper Maintenance Utilities")
    parser.add_argument('--deduplicate', action='store_true', help='Remove duplicate questions')
    parser.add_argument('--clean-csv', action='store_true', help='Clean CSV formatting')
    parser.add_argument('--fix-descriptions', action='store_true', help='Fix missing descriptions')
    parser.add_argument('--analyze-duplicates', action='store_true', help='Analyze duplicate patterns')
    parser.add_argument('--all', action='store_true', help='Run all maintenance tasks')
    parser.add_argument('--output-dir', default='output', help='Output directory (default: output)')
    
    args = parser.parse_args()
    
    if not any([args.deduplicate, args.clean_csv, args.fix_descriptions, 
               args.analyze_duplicates, args.all]):
        parser.print_help()
        return
    
    maintenance = MaintenanceManager(args.output_dir)
    
    print("🛠️  FunTrivia Scraper Maintenance Utilities")
    print("=" * 50)
    
    if args.all or args.analyze_duplicates:
        maintenance.analyze_duplicates()
        print()
    
    if args.all or args.deduplicate:
        maintenance.deduplicate_questions()
        print()
    
    if args.all or args.clean_csv:
        maintenance.clean_csv_columns()
        print()
    
    if args.all or args.fix_descriptions:
        maintenance.fix_missing_descriptions()
        print()
    
    print("✅ Maintenance tasks completed!")

if __name__ == "__main__":
    main() 