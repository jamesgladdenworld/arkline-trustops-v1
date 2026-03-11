import json
from typing import List, Dict, Any
from anthropic import Anthropic
from config import BATCH_SIZE, CLAUDE_MODEL


class ResponseGenerator:
    """Generate responses using Claude Opus 4.6."""
    
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = CLAUDE_MODEL
    
    def generate_batch(self, questions: List[Dict], docs: str) -> List[Dict[str, Any]]:
        responses = []
        
        for i in range(0, len(questions), BATCH_SIZE):
            batch = questions[i:i+BATCH_SIZE]
            batch_responses = self._process_batch(batch, docs)
            responses.extend(batch_responses)
        
        return responses
    
    def _process_batch(self, batch: List[Dict], docs: str) -> List[Dict[str, Any]]:
        questions_text = "\n".join([
            f"{q['number']}. {q['question']}"
            for q in batch
        ])
        
        prompt = f"""You are a security compliance expert. Answer the following security questionnaire questions based on the provided documentation.

DOCUMENTATION:
{docs}

QUESTIONS:
{questions_text}

For each question, provide a clear, concise answer grounded in the documentation.

Format your response as JSON with this structure:
{{
  "responses": [
    {{"number": "1", "answer": "...", "confidence": 0.95}},
    {{"number": "2", "answer": "...", "confidence": 0.85}}
  ]
}}
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            
            try:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
                
                responses = []
                for resp in data.get('responses', []):
                    q_num = str(resp.get('number', ''))
                    question = next((q for q in batch if str(q['number']) == q_num), None)
                    
                    if question:
                        responses.append({
                            'number': q_num,
                            'question': question['question'],
                            'answer': resp.get('answer', ''),
                            'confidence': resp.get('confidence', 0.8),
                            'row': question['row'],
                            'cell_ref': question['cell_ref']
                        })
                
                return responses
            
            except json.JSONDecodeError:
                print(f"Warning: Failed to parse JSON response")
                return []
        
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return []
