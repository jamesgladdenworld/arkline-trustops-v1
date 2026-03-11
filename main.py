#!/usr/bin/env python3
"""
Arkline TrustOps v1 - AI-Powered Security Questionnaire Completion Tool

Main entry point orchestrating the full workflow:
1. Parse Excel questionnaire
2. Load compliance documentation
3. Generate responses using Claude Opus 4.6
4. Human review of generated responses
5. Export completed questionnaire to Excel
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from parsers import ExcelParser, DocLoader
from agents import ResponseGenerator, ResponseReviewer
from exporters import ExcelExporter
from config import INPUT_DIR, OUTPUT_DIR


def main():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment variables")
        print("Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    
    print("🚀 Arkline TrustOps v1 - Security Questionnaire Completion Tool")
    print("="*80)
    
    # Step 1: Parse questionnaire
    print("\n📋 Step 1: Parsing questionnaire...")
    questionnaire_path = INPUT_DIR / "questionnaire.xlsx"
    
    if not questionnaire_path.exists():
        print(f"❌ Error: {questionnaire_path} not found")
        print(f"Please place your questionnaire at: {questionnaire_path}")
        sys.exit(1)
    
    parser = ExcelParser(str(questionnaire_path))
    questions = parser.parse()
    print(f"✅ Parsed {len(questions)} questions")
    
    # Step 2: Load compliance documentation
    print("\n📚 Step 2: Loading compliance documentation...")
    doc_loader = DocLoader(INPUT_DIR / "compliance_docs")
    docs = doc_loader.load_all()
    
    if not docs:
        print("⚠️  Warning: No compliance documents found")
        print(f"Place documents in: {INPUT_DIR / 'compliance_docs'}")
        docs = "No documentation provided."
    else:
        print(f"✅ Loaded compliance documentation ({len(docs)} characters)")
    
    # Step 3: Generate responses
    print("\n🤖 Step 3: Generating responses with Claude Opus 4.6...")
    generator = ResponseGenerator(api_key)
    responses = generator.generate_batch(questions, docs)
    print(f"✅ Generated {len(responses)} responses")
    
    if not responses:
        print("❌ No responses generated. Check your API key and try again.")
        sys.exit(1)
    
    # Step 4: Human review
    print("\n👤 Step 4: Human review of generated responses...")
    print("Review each response and approve, edit, or reject.")
    
    try:
        reviewer = ResponseReviewer(responses)
        review_results = reviewer.review_all()
        reviewer.print_summary()
    except KeyboardInterrupt:
        print("\n⚠️  Review interrupted by user")
        sys.exit(0)
    
    # Step 5: Export results
    print("\n💾 Step 5: Exporting completed questionnaire...")
    output_path = OUTPUT_DIR / f"questionnaire_completed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    exporter = ExcelExporter(str(questionnaire_path), str(output_path))
    exporter.export_responses(review_results['approved'])
    
    # Export summary
    summary = {
        'total': len(questions),
        'approved': len(review_results['approved']),
        'rejected': len(review_results['rejected']),
        'edited': len(review_results['edited']),
        'completion_rate': len(review_results['approved']) / len(questions) if questions else 0,
        'timestamp': datetime.now().isoformat()
    }
    
    summary_path = OUTPUT_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    exporter.export_summary(summary, str(summary_path))
    
    print("\n" + "="*80)
    print("✅ Questionnaire completion workflow finished!")
    print(f"📁 Output files:")
    print(f"   - Completed questionnaire: {output_path}")
    print(f"   - Summary: {summary_path}")
    print("="*80)


if __name__ == "__main__":
    main()
