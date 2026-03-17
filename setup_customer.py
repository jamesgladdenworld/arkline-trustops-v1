#!/usr/bin/env python3
"""Setup a new customer or questionnaire directory structure."""

import sys
from pathlib import Path

def setup_questionnaire(customer_name: str, questionnaire_name: str = None):
    """Create directory structure for a customer and/or specific questionnaire."""
    
    # If no questionnaire name provided, create customer-level structure
    if questionnaire_name is None:
        base_dir = Path("customers") / customer_name
        shared_docs_dir = base_dir / "shared_compliance_docs"
        
        # Create shared compliance docs folder
        shared_docs_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n✅ Customer directory created: {base_dir}")
        print(f"   📁 Shared compliance docs: {shared_docs_dir}/")
        print(f"\n📝 Next steps:")
        print(f"   1. Add shared compliance docs to: {shared_docs_dir}/")
        print(f"      (SOC 2 reports, ISO 27001 certs, etc.)")
        print(f"   2. Setup first questionnaire:")
        print(f"      python3 setup_customer.py {customer_name} questionnaire_001")
        print()
    else:
        # Create questionnaire-specific structure
        base_dir = Path("customers") / customer_name / questionnaire_name
        input_dir = base_dir / "input"
        compliance_dir = input_dir / "compliance_docs"
        output_dir = base_dir / "output"
        logs_dir = base_dir / "logs"
        
        # Create all directories
        compliance_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        shared_docs_dir = Path("customers") / customer_name / "shared_compliance_docs"
        
        print(f"\n✅ Questionnaire directory created: {base_dir}")
        print(f"   📁 Input: {input_dir}/")
        print(f"   📁 Compliance docs: {compliance_dir}/")
        print(f"   📁 Output: {output_dir}/")
        print(f"   📁 Logs: {logs_dir}/")
        print(f"\n📝 Next steps:")
        print(f"   1. Add questionnaire.xlsx to: {input_dir}/")
        print(f"   2. Add questionnaire-specific docs to: {compliance_dir}/")
        print(f"   3. Shared docs available at: {shared_docs_dir}/")
        print(f"   4. Run: python3 main.py {customer_name}/{questionnaire_name}")
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 setup_customer.py <customer_name>")
        print("  python3 setup_customer.py <customer_name> <questionnaire_name>")
        print("\nExamples:")
        print("  python3 setup_customer.py acme_saas")
        print("  python3 setup_customer.py acme_saas questionnaire_001")
        print("  python3 setup_customer.py acme_saas stripe_vendor_form")
        sys.exit(1)
    
    customer_name = sys.argv[1]
    questionnaire_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    setup_questionnaire(customer_name, questionnaire_name)
