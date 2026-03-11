import openpyxl
from typing import List, Dict, Any


class ExcelParser:
    """Parse Excel questionnaires and extract questions."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.workbook = None
        self.worksheet = None
    
    def extract_questions(self) -> List[Dict[str, Any]]:
        try:
            self.workbook = openpyxl.load_workbook(self.filepath)
            self.worksheet = self.workbook.active
            
            questions = []
            
            for row_idx, row in enumerate(self.worksheet.iter_rows(min_row=2, values_only=False), start=2):
                if not row[0].value:
                    continue
                
                question_num = row[0].value
                question_text = row[1].value if len(row) > 1 else None
                
                if question_text:
                    questions.append({
                        'number': question_num,
                        'question': str(question_text),
                        'row': row_idx,
                        'cell_ref': f'C{row_idx}'
                    })
            
            return questions
        
        except Exception as e:
            raise FileNotFoundError(f"Failed to parse Excel: {e}")
    
    def close(self):
        if self.workbook:
            self.workbook.close()
