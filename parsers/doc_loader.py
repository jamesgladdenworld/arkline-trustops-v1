from pathlib import Path
from typing import Optional


class DocLoader:
    """Load compliance documentation from files."""
    
    def __init__(self, docs_dir: str):
        self.docs_dir = Path(docs_dir)
    
    def load_all(self) -> str:
        """Load all documents from the directory."""
        if not self.docs_dir.exists():
            return ""
        
        all_docs = []
        
        # Load text files
        for txt_file in self.docs_dir.glob("*.txt"):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    all_docs.append(f"--- {txt_file.name} ---\n{content}")
            except Exception as e:
                print(f"Warning: Could not read {txt_file}: {e}")
        
        # Load PDF files (if pdfplumber is available)
        try:
            import pdfplumber
            for pdf_file in self.docs_dir.glob("*.pdf"):
                try:
                    with pdfplumber.open(pdf_file) as pdf:
                        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
                        all_docs.append(f"--- {pdf_file.name} ---\n{text}")
                except Exception as e:
                    print(f"Warning: Could not read {pdf_file}: {e}")
        except ImportError:
            pass
        
        # Load DOCX files (if python-docx is available)
        try:
            from docx import Document
            for docx_file in self.docs_dir.glob("*.docx"):
                try:
                    doc = Document(docx_file)
                    text = "\n".join([para.text for para in doc.paragraphs])
                    all_docs.append(f"--- {docx_file.name} ---\n{text}")
                except Exception as e:
                    print(f"Warning: Could not read {docx_file}: {e}")
        except ImportError:
            pass
        
        return "\n\n".join(all_docs)
