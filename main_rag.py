#!/usr/bin/env python3
"""
Arkline TrustOps - Main Entry Point with RAG Pipeline Integration
Processes vendor security questionnaires using RAG-enhanced Claude responses
with citations and confidence scoring
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers.excel_parser import ExcelParser
from agents.response_reviewer import ResponseReviewer
from exporters.excel_exporter import ExcelExporter
from rag_pipeline import RAGPipeline
from answer_generator import AnswerGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class ArklineWithRAG:
    """Main orchestrator for Arkline with RAG pipeline"""
    
    def __init__(self):
        self.rag_pipeline = RAGPipeline()
        self.answer_generator = AnswerGenerator(self.rag_pipeline)
        self.reviewer = ResponseReviewer()
        self.exporter = ExcelExporter()
    
    def process_questionnaire_with_rag(self, customer_path: str):
        """
        Process a questionnaire using RAG pipeline with citations and confidence
        
        Args:
            customer_path: Path to customer/questionnaire directory
                          e.g., "acme_saas/questionnaire_001"
        """
        base_path = Path("customers") / customer_path
        
        if not base_path.exists():
            logger.error(f"Customer path not found: {base_path}")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {customer_path}")
        logger.info(f"{'='*60}\n")
        
        # Step 1: Load compliance documents into RAG
        logger.info("📚 Loading compliance documents into RAG pipeline...")
        compliance_docs = self._get_compliance_docs(base_path)
        
        if compliance_docs:
            chunks = self.rag_pipeline.ingest_documents(compliance_docs)
            logger.info(f"✅ Loaded {len(compliance_docs)} documents ({chunks} chunks)")
            
            # Show RAG stats
            stats = self.rag_pipeline.get_stats()
            logger.info(f"   - Total chunks: {stats['total_chunks']}")
            logger.info(f"   - Documents: {stats['total_documents']}\n")
        else:
            logger.warning("⚠️  No compliance documents found. Proceeding without RAG context.\n")
        
        # Step 2: Parse questionnaire
        logger.info("📋 Parsing questionnaire...")
        questionnaire_file = base_path / "input" / "questionnaire.xlsx"
        
        if not questionnaire_file.exists():
            logger.error(f"Questionnaire not found: {questionnaire_file}")
            return
        
        parser = ExcelParser(str(questionnaire_file))
        questions = parser.parse()
        logger.info(f"✅ Parsed {len(questions)} questions\n")
        
        # Step 3: Generate responses with RAG
        logger.info("🤖 Generating responses with RAG pipeline...")
        responses = self._generate_responses_with_rag(questions)
        logger.info(f"✅ Generated {len(responses)} responses\n")
        
        # Step 4: Interactive review
        logger.info("👤 Starting interactive review process...")
        reviewed_responses = self.reviewer.review_responses_interactive(responses)
        logger.info(f"✅ Review complete\n")
        
        # Step 5: Export results
        logger.info("💾 Exporting results...")
        output_file = base_path / "output" / "completed_questionnaire.xlsx"
        self.exporter.export(reviewed_responses, str(output_file))
        logger.info(f"✅ Results exported to: {output_file}\n")
        
        logger.info(f"{'='*60}")
        logger.info("✨ Questionnaire processing complete!")
        logger.info(f"{'='*60}\n")
    
    def _get_compliance_docs(self, base_path: Path) -> List[str]:
        """Get all compliance documents for a questionnaire"""
        doc_paths = []
        
        # Check shared compliance docs (used for all questionnaires)
        shared_docs_path = base_path.parent / "shared_compliance_docs"
        if shared_docs_path.exists():
            for file in shared_docs_path.glob("*"):
                if file.suffix.lower() in ['.pdf', '.txt', '.docx']:
                    doc_paths.append(str(file))
        
        # Check questionnaire-specific docs
        questionnaire_docs_path = base_path / "input" / "compliance_docs"
        if questionnaire_docs_path.exists():
            for file in questionnaire_docs_path.glob("*"):
                if file.suffix.lower() in ['.pdf', '.txt', '.docx']:
                    doc_paths.append(str(file))
        
        return doc_paths
    
    def _generate_responses_with_rag(self, questions: List[str]) -> List[Dict]:
        """Generate responses using RAG-enhanced context with citations and confidence"""
        responses = []
        
        for i, question in enumerate(questions, 1):
            logger.info(f"  [{i}/{len(questions)}] Processing question...")
            
            try:
                # Generate answer with citations and confidence
                generated_answer = self.answer_generator.generate_answer(question)
                
                # Log confidence and review status
                confidence_pct = generated_answer.confidence_score * 100
                review_flag = "⚠️  REVIEW" if generated_answer.requires_manual_review else "✅ OK"
                logger.info(f"      Confidence: {confidence_pct:.0f}% | {review_flag}")
                
                responses.append({
                    "question": question,
                    "response": generated_answer.answer,
                    "citations": [
                        {
                            "source_file": c.source_file,
                            "chunk_id": c.chunk_id,
                            "similarity_score": c.similarity_score,
                            "excerpt": c.excerpt
                        }
                        for c in generated_answer.citations
                    ],
                    "confidence_score": generated_answer.confidence_score,
                    "has_sufficient_evidence": generated_answer.has_sufficient_evidence,
                    "requires_manual_review": generated_answer.requires_manual_review,
                    "status": "generated"
                })
            
            except Exception as e:
                logger.error(f"Error on question {i}: {e}")
                responses.append({
                    "question": question,
                    "response": f"Error: {str(e)}",
                    "citations": [],
                    "confidence_score": 0.0,
                    "has_sufficient_evidence": False,
                    "requires_manual_review": True,
                    "status": "error"
                })
        
        return responses


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 main_rag.py <customer_path>")
        print("Example: python3 main_rag.py acme_saas/questionnaire_001")
        sys.exit(1)
    
    customer_path = sys.argv[1]
    
    arkline = ArklineWithRAG()
    arkline.process_questionnaire_with_rag(customer_path)


if __name__ == "__main__":
    main()
