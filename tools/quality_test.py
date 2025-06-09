#!/usr/bin/env python3
"""
Quick Quality Test for FunTrivia Scraper

Tests correctness of:
- Answer extraction
- Description extraction  
- Domain/topic/difficulty mapping
- Duplicate detection

Usage: python3 tools/quality_test.py
"""

import sys
import pandas as pd
from pathlib import Path

def test_csv_quality():
    """Test quality of existing CSV files."""
    print("🧪 КАЧЕСТВЕННЫЙ АНАЛИЗ CSV")
    print("=" * 50)
    
    output_dir = Path("output")
    csv_files = ["multiple_choice.csv", "true_false.csv", "sound.csv"]
    
    total_questions = 0
    issues = {
        'missing_answers': 0,
        'missing_descriptions': 0,
        'unmapped_domains': 0,
        'unmapped_difficulties': 0,
        'potential_duplicates': 0
    }
    
    all_questions = []
    
    for csv_file in csv_files:
        csv_path = output_dir / csv_file
        if not csv_path.exists():
            print(f"📂 {csv_file}: Не найден")
            continue
        
        df = pd.read_csv(csv_path)
        print(f"📄 {csv_file}: {len(df)} вопросов")
        
        # Check missing answers
        missing_answers = df['CorrectAnswer'].isna().sum()
        issues['missing_answers'] += missing_answers
        if missing_answers > 0:
            print(f"  ⚠️  {missing_answers} вопросов без правильного ответа")
        
        # Check missing descriptions
        missing_desc = df['Description'].isna().sum()
        issues['missing_descriptions'] += missing_desc
        if missing_desc > 0:
            print(f"  ⚠️  {missing_desc} вопросов без описания")
        
        # Check domain mapping
        unique_domains = df['Domain'].unique()
        expected_domains = ['Nature', 'Science', 'Geography', 'Culture', 'Sports', 'History', 'Religion', 'Education']
        unmapped_domains = [d for d in unique_domains if d not in expected_domains]
        if unmapped_domains:
            print(f"  ⚠️  Неожиданные домены: {unmapped_domains}")
            issues['unmapped_domains'] += len(unmapped_domains)
        
        # Check difficulty mapping
        unique_difficulties = df['Difficulty'].unique()
        expected_difficulties = ['Easy', 'Normal', 'Hard']
        unmapped_diff = [d for d in unique_difficulties if d not in expected_difficulties]
        if unmapped_diff:
            print(f"  ⚠️  Неожиданные сложности: {unmapped_diff}")
            issues['unmapped_difficulties'] += len(unmapped_diff)
        
        # Collect for duplicate analysis
        for _, row in df.iterrows():
            all_questions.append({
                'question': str(row.get('Question', '')).strip().lower(),
                'answer': str(row.get('CorrectAnswer', '')).strip().lower(),
                'file': csv_file
            })
        
        total_questions += len(df)
    
    # Duplicate detection
    seen_signatures = set()
    for q in all_questions:
        signature = f"{q['question']}|{q['answer']}"
        if signature in seen_signatures:
            issues['potential_duplicates'] += 1
        seen_signatures.add(signature)
    
    # Summary
    print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"  Всего вопросов: {total_questions}")
    print(f"  Потенциальные дубликаты: {issues['potential_duplicates']}")
    print(f"  Пропущенные ответы: {issues['missing_answers']}")
    print(f"  Пропущенные описания: {issues['missing_descriptions']}")
    print(f"  Проблемы маппинга: {issues['unmapped_domains'] + issues['unmapped_difficulties']}")
    
    # Quality score
    quality_score = 100
    if total_questions > 0:
        quality_score -= (issues['missing_answers'] / total_questions) * 30
        quality_score -= (issues['missing_descriptions'] / total_questions) * 20
        quality_score -= (issues['potential_duplicates'] / total_questions) * 25
        quality_score -= ((issues['unmapped_domains'] + issues['unmapped_difficulties']) / total_questions) * 25
    
    quality_score = max(0, quality_score)
    
    print(f"\n🎯 ОЦЕНКА КАЧЕСТВА: {quality_score:.1f}/100")
    
    if quality_score >= 90:
        print("✅ ОТЛИЧНОЕ качество данных!")
    elif quality_score >= 75:
        print("🟡 ХОРОШЕЕ качество данных")
    elif quality_score >= 60:
        print("🟠 ПРИЕМЛЕМОЕ качество данных")
    else:
        print("🔴 ТРЕБУЕТСЯ улучшение качества")
    
    return issues, quality_score

def test_sample_extraction():
    """Test extraction on a small sample."""
    print(f"\n🔬 ТЕСТ ИЗВЛЕЧЕНИЯ ДАННЫХ")
    print("=" * 50)
    print("Запустите: python3 src/main.py --max-questions 5 --dry-run")
    print("Для тестирования извлечения данных")

if __name__ == "__main__":
    # Test existing data quality
    issues, score = test_csv_quality()
    
    # Recommendations
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    if issues['missing_descriptions'] > 0:
        print(f"  - Запустите: python3 tools/maintenance.py --fix-descriptions")
    if issues['potential_duplicates'] > 0:
        print(f"  - Запустите: python3 tools/maintenance.py --deduplicate")
    if issues['missing_answers'] > 0:
        print(f"  - Проверьте алгоритмы извлечения ответов")
    
    print(f"\n🚀 Для тестирования нового батча:")
    print(f"  python3 tools/batch_scraper.py --batch-size 3 --parallel-jobs 1 --questions-per-batch 20") 