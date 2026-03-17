#!/usr/bin/env python3
"""
Arkline TrustOps v1 - AI-Powered Security Questionnaire Completion Tool

Main entry point orchestrating the full workflow:
1. Parse Excel questionnaire
2. Load compliance documentation (questionnaire-specific + shared)
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


def main(customer_questionnaire_path: str):
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment variables")
        print("Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    
    # Parse the path: either "customer_name" or "customer_name/questionnaire_name"
    path_parts = customer_questionnaire_path.split('/')
    
    if len(path_parts) == 1:
        # Only customer name provided - error
        print(f"❌ Error: Please specify a questionnaire")
        print(f"Usage: python3 main.py <customer_name>/<questionnaire_name>")
        print(f"Example: python3 main.py acme_saas/questionnaire_001")
        sys.exit(1)
    elif len(path_parts) == 2:
        customer_name = path_parts[0]
        questionnaire_name = path_parts[1]
    else:
        print(f"❌ Error: Invalid path format")
        print(f"Usage: python3 main.py <customer_name>/<questionnaire_name>")
        sys.exit(1)
    
    # Setup directories
    customer_dir = Path("customers") / customer_name
    questionnaire_dir = customer_dir / questionnaire_name
    input_dir = questionnaire_dir / "input"
    output_dir = questionnaire_dir / "output"
    logs_dir = questionnaire_dir / "logs"
    shared_docs_dir = customer_dir / "shared_compliance_docs"
    
    print("\n🚀 Arkline TrustOps v1 - Security Questionnaire Completion Tool")
    print(f"👥 Customer: {customer_name}")
    print(f"📋 Questionnaire: {questionnaire_name}")
    print("="*80)
    
    # Validate questionnaire directory exists
    if not input_dir.exists():
        print(f"❌ Error: Questionnaire directory not found: {input_dir}")
        print(f"Run this first: python3 setup_customer.py {customer_name} {questionnaire_name}")
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
    
    # Load questionnaire-specific docs
    compliance_docs_dir = input_dir / "compliance_docs"
    doc_loader = DocLoader(str(compliance_docs_dir))
    questionnaire_docs = doc_loader.load_all()
    
    # Load shared customer docs
    shared_docs = ""
    if shared_docs_dir.exists():
        shared_loader = DocLoader(str(shared_docs_dir))
        shared_docs = shared_loader.load_all()
    
    # Combine all docs
    all_docs = questionnaire_docs
    if shared_docs:
        all_docs = f"{questionnaire_docs}\n\n--- SHARED CUSTOMER DOCUMENTATION ---\n\n{shared_docs}"
    
    if not all_docs or all_docs.strip() == "":
        print("⚠️  Warning: No compliance documents found")
        all_docs = "No documentation provided."
    else:
        print(f"✅ Loaded compliance documentation ({len(all_docs)} characters)")
        if questionnaire_docs:
            print(f"   - Questionnaire-specific docs: {len(questionnaire_docs)} characters")
        if shared_docs:
            print(f"   - Shared customer docs: {len(shared_docs)} characters")
    
    # Step 3: Generate responses
    print("\n🤖 Step 3: Generating responses with Claude Opus 4.6...")
    generator = ResponseGenerator(api_key)
    responses = generator.generate_batch(questions, all_docs)
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
        'timestamp': datetime.now().isoformat(),
        'customer': customer_name,
        'questionnaire': questionnaire_name
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
        print("Usage: python3 main.py <customer_name>/<questionnaire_name>")
        print("\nExamples:")
        print("  python3 main.py acme_saas/questionnaire_001")
        print("  python3 main.py techstartup_inc/stripe_vendor_form")
        print("  python3 main.py fintech_solutions/okta_questionnaire")
        print("\nFirst, setup the customer and questionnaire directories:")
        print("  python3 setup_customer.py acme_saas")
        print("  python3 setup_customer.py acme_saas questionnaire_001")
        sys.exit(1)
    
    customer_questionnaire_path = sys.argv[1]
    main(customer_questionnaire_path)
