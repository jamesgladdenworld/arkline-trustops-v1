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


def main(customer_name: str):
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment variables")
        print("Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    
    # Setup customer directories
    customer_dir = Path("customers") / customer_name
    input_dir = customer_dir / "input"
    output_dir = customer_dir / "output"
    logs_dir = customer_dir / "logs"
    
    print("\n🚀 Arkline TrustOps v1 - Security Questionnaire Completion Tool")
    print(f"📊 Customer: {customer_name}")
    print("="*80)
    
    # Validate customer directory exists
    if not input_dir.exists():
        print(f"❌ Error: Customer directory not found: {input_dir}")
        print(f"Run this first: python3 setup_customer.py {customer_name}")
        sys.exit(1)
    
    # Step 1: Parse questionnaire
    print("\n📋 Step 1: Parsing questionnaire...")
    questionnaire_path = input_dir / "questionnaire.xlsx"
    
    if not questionnaire_path.exists():
        print(f"❌ Error: {questionnaire_path} not found")
        sys.exit(1)
    
    parser = ExcelParser(str(questionnaire_path))
    questions = parser.parse()
    print(f"✅ Parsed {len(questions)} questions")
    
    # Step 2: Load compliance documentation
    print("\n📚 Step 2: Loading compliance documentation...")
    compliance_docs_dir = input_dir / "compliance_docs"
    doc_loader = DocLoader(str(compliance_docs_dir))
    docs = doc_loader.load_all()
    
    if not docs:
        print("⚠️  Warning: No compliance documents found")
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
    output_path = output_dir / f"questionnaire_completed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
    
    summary_path = output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    exporter.export_summary(summary, str(summary_path))
    
    print("\n" + "="*80)
    print("✅ Questionnaire completion workflow finished!")
    print(f"📁 Output files:")
    print(f"   - Completed questionnaire: {output_path}")
    print(f"   - Summary: {summary_path}")
    print("="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 main.py <customer_name>")
        print("Example: python3 main.py acme_saas")
        print("\nFirst, setup the customer directory:")
        print("  python3 setup_customer.py acme_saas")
        sys.exit(1)
    
    customer_name = sys.argv[1]
    main(customer_name)
