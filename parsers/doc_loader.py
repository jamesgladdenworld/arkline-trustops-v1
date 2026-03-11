import os
from pathlib import Path
from typing import Dict, List
import pdfplumber


class DocLoader:
    """Load and process compliance documentation."""
    
    def __init__(self, docs_dir: str):
        self.docs_dir = Path(docs_dir)
        self.docs = {}
    
    def load_all_docs(self) -> Dict[str, str]:
        docs = {}
        
        if not self.docs_dir.exists():
            return docs
        
        for txt_file in self.docs_dir.glob('*.txt'):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    docs[txt_file.name] = f.read()
            except Exception as e:
                print(f"Warning: Failed to load {txt_file.name}: {e}")
        
        for pdf_file in self.docs_dir.glob('*.pdf'):
            try:
                text = ""
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                docs[pdf_file.name] = text
            except Exception as e:
                print(f"Warning: Failed to load {pdf_file.name}: {e}")
        
        self.docs = docs
        return docs
    
    def combine_docs(self, docs: Dict[str, str]) -> str:
        combined = ""
        for filename, content in docs.items():
            combined += f"\n\n--- Document: {filename} ---\n{content}"
        return combined
    
    def get_doc_summary(self, docs: Dict[str, str]) -> Dict[str, int]:
        return {name: len(content) for name, content in docs.items()}
