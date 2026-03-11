import json
from typing import Dict, List, Any
from pathlib import Path


class ResponseReviewer:
    """Interactive human review of generated responses."""
    
    def __init__(self, responses: List[Dict[str, Any]]):
        self.responses = responses
        self.approved = []
        self.rejected = []
        self.edited = {}
    
    def review_all(self) -> Dict[str, List]:
        for idx, response in enumerate(self.responses, 1):
            self._review_single(response, idx)
        
        return {
            'approved': self.approved,
            'rejected': self.rejected,
            'edited': self.edited
        }
    
    def _review_single(self, response: Dict, idx: int):
        print(f"\n{'='*80}")
        print(f"Question {idx}/{len(self.responses)}: {response['number']}")
        print(f"{'='*80}")
        print(f"\n{response['question']}")
        print(f"\nGenerated Answer (Confidence: {response['confidence']:.0%}):")
        print(f"{response['answer']}")
        print(f"\nOptions: [A]pprove, [E]dit, [R]eject, [S]kip, [Q]uit")
        
        while True:
            choice = input("\nYour choice: ").strip().upper()
            
            if choice == 'A':
                self.approved.append(response)
                print("✅ Approved")
                break
            elif choice == 'E':
                edited_answer = input("\nEnter edited answer: ").strip()
                response['answer'] = edited_answer
                self.approved.append(response)
                self.edited[response['number']] = edited_answer
                print("✅ Edited and approved")
                break
            elif choice == 'R':
                self.rejected.append(response)
                print("❌ Rejected")
                break
            elif choice == 'S':
                print("⏭️  Skipped")
                break
            elif choice == 'Q':
                print("\n⚠️  Exiting review...")
                raise KeyboardInterrupt()
            else:
                print("Invalid choice. Please try again.")
    
    def save_review_state(self, filepath: str):
        state = {
            'approved': self.approved,
            'rejected': self.rejected,
            'edited': self.edited
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def print_summary(self):
        print(f"\n{'='*80}")
        print("Review Summary")
        print(f"{'='*80}")
        print(f"Approved: {len(self.approved)}")
        print(f"Rejected: {len(self.rejected)}")
        print(f"Edited: {len(self.edited)}")
        print(f"{'='*80}")
