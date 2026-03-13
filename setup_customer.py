#!/usr/bin/env python3
"""Setup a new customer directory structure."""

import sys
from pathlib import Path

def setup_customer(customer_name: str):
    """Create directory structure for a new customer."""
    
    base_dir = Path("customers") / customer_name
    input_dir = base_dir / "input"
    compliance_dir = input_dir / "compliance_docs"
    output_dir = base_dir / "output"
    logs_dir = base_dir / "logs"
    
    # Create all directories
    compliance_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n✅ Customer directory created: {base_dir}")
    print(f"   📁 Input: {input_dir}/")
    print(f"   📁 Compliance docs: {compliance_dir}/")
    print(f"   📁 Output: {output_dir}/")
    print(f"   📁 Logs: {logs_dir}/")
    print(f"\n📝 Next steps:")
    print(f"   1. Add questionnaire.xlsx to: {input_dir}/")
    print(f"   2. Add compliance docs (.pdf, .txt, .docx) to: {compliance_dir}/")
    print(f"   3. Run: python3 main.py {customer_name}")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 setup_customer.py <customer_name>")
        print("Example: python3 setup_customer.py acme_saas")
        sys.exit(1)
    
    customer_name = sys.argv[1]
    setup_customer(customer_name)
