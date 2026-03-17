"""
Answer Generator - Generates audit-ready answers with citations and confidence scores
Wraps RAG pipeline and Claude API for professional compliance responses
"""

import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import anthropic

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Represents a citation to a source document"""
    source_file: str
    chunk_id: int
    similarity_score: float
    excerpt: str


@dataclass
class GeneratedAnswer:
    """Complete answer with citations and confidence"""
    question: str
    answer: str
    citations: List[Citation]
    confidence_score: float
    has_sufficient_evidence: bool
    requires_manual_review: bool
    metadata: Dict


class AnswerGenerator:
    """
    Generates audit-ready answers with citations and confidence scoring
    
    Combines RAG pipeline context with Claude Opus 4.6 to produce
    professional, traceable compliance answers.
    """
    
    def __init__(self, rag_pipeline, api_key: Optional[str] = None):
        """
        Initialize Answer Generator
        
        Args:
            rag_pipeline: RAGPipeline instance for document retrieval
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.rag_pipeline = rag_pipeline
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate_answer(self, question: str, max_tokens: int = 1024) -> GeneratedAnswer:
        """
        Generate a complete answer with citations and confidence
        
        Args:
            question: The question to answer
            max_tokens: Maximum tokens for the answer
            
        Returns:
            GeneratedAnswer with full metadata
        """
        logger.info(f"Generating answer for: {question[:60]}...")
        
        # Step 1: Retrieve relevant chunks from RAG
        relevant_chunks = self.rag_pipeline.retrieve_relevant_chunks(question, top_k=10)
        
        # Step 2: Calculate evidence sufficiency
        has_sufficient_evidence = len(relevant_chunks) > 0 and relevant_chunks[0].similarity_score > 0.3
        
        # Step 3: Build citations from retrieved chunks
        citations = self._build_citations(relevant_chunks)
        
        # Step 4: Generate answer with Claude
        answer_text = self._generate_with_claude(question, relevant_chunks, has_sufficient_evidence)
        
        # Step 5: Calculate confidence score
        confidence_score = self._calculate_confidence(relevant_chunks, answer_text)
        
        # Step 6: Determine if manual review is needed
        requires_manual_review = not has_sufficient_evidence or confidence_score < 0.6
        
        # Step 7: Build metadata
        metadata = {
            "retrieved_chunks": len(relevant_chunks),
            "avg_similarity": sum(c.similarity_score for c in relevant_chunks) / len(relevant_chunks) if relevant_chunks else 0,
            "model": "claude-opus-4.6",
            "timestamp": self._get_timestamp()
        }
        
        return GeneratedAnswer(
            question=question,
            answer=answer_text,
            citations=citations,
            confidence_score=confidence_score,
            has_sufficient_evidence=has_sufficient_evidence,
            requires_manual_review=requires_manual_review,
            metadata=metadata
        )
    
    def _build_citations(self, chunks) -> List[Citation]:
        """Build citations from retrieved chunks"""
        citations = []
        
        for chunk in chunks:
            # Limit excerpt to first 200 chars
            excerpt = chunk.content[:200].replace('\n', ' ').strip()
            if len(chunk.content) > 200:
                excerpt += "..."
            
            citation = Citation(
                source_file=Path(chunk.source).name,
                chunk_id=chunk.chunk_id,
                similarity_score=chunk.similarity_score if hasattr(chunk, 'similarity_score') else 0.0,
                excerpt=excerpt
            )
            citations.append(citation)
        
        return citations
    
    def _generate_with_claude(self, question: str, chunks, has_evidence: bool) -> str:
        """Generate answer using Claude with RAG context"""
        
        # Build context string from chunks
        if chunks:
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                source = Path(chunk.source).name
                context_parts.append(f"[Source {i}: {source}]\n{chunk.content}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant documentation found."
        
        # Adjust system prompt based on evidence availability
        if has_evidence:
            system_prompt = """You are a security compliance expert helping companies complete vendor security questionnaires.

Your responses should be:
- Accurate and based on the provided compliance documentation
- Specific, detailed, and audit-ready
- Professional and suitable for security auditors
- Aligned with security best practices
- Honest about capabilities and limitations

CRITICAL: If the documentation does not contain sufficient information to answer the question, respond with:
"Insufficient evidence in documentation. This question requires manual review based on company-specific policies."

Always cite the relevant documentation sections in your answer."""
        else:
            system_prompt = """You are a security compliance expert helping companies complete vendor security questionnaires.

IMPORTANT: The available documentation does NOT contain sufficient information to answer this question properly.

Provide the best answer you can based on general security practices, but clearly note that this answer is NOT backed by company documentation and requires manual review.

Format: Start with "⚠️ INSUFFICIENT DOCUMENTATION:" and then provide your best-effort answer."""
        
        user_prompt = f"""Based on the following compliance documentation, answer this security questionnaire question:

QUESTION: {question}

RELEVANT DOCUMENTATION:
{context}

Provide a comprehensive, professional answer suitable for security auditors."""
        
        try:
            message = self.client.messages.create(
                model="claude-opus-4.6",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return message.content[0].text
        
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Error generating answer: {str(e)}"
    
    def _calculate_confidence(self, chunks, answer_text: str) -> float:
        """
        Calculate confidence score (0-1) based on:
        1. Number and quality of retrieved chunks
        2. Similarity scores
        3. Answer characteristics
        """
        
        if not chunks:
            return 0.0
        
        # Factor 1: Average similarity score (0-1)
        avg_similarity = sum(c.similarity_score if hasattr(c, 'similarity_score') else 0 for c in chunks) / len(chunks)
        
        # Factor 2: Number of relevant chunks (normalized)
        chunk_factor = min(len(chunks) / 5.0, 1.0)  # Max out at 5 chunks
        
        # Factor 3: Answer length (longer = more detailed = more confident)
        # Normalize to 0-1, where 500 chars = full confidence
        answer_factor = min(len(answer_text) / 500.0, 1.0)
        
        # Factor 4: Check for uncertainty markers in answer
        uncertainty_markers = [
            "insufficient evidence",
            "not documented",
            "unclear",
            "unable to determine",
            "requires manual review"
        ]
        
        has_uncertainty = any(marker in answer_text.lower() for marker in uncertainty_markers)
        uncertainty_factor = 0.5 if has_uncertainty else 1.0
        
        # Weighted average
        confidence = (
            avg_similarity * 0.4 +      # 40% weight on semantic similarity
            chunk_factor * 0.3 +         # 30% weight on number of chunks
            answer_factor * 0.2 +        # 20% weight on answer length
            uncertainty_factor * 0.1     # 10% weight on uncertainty markers
        )
        
        return round(confidence, 2)
    
    def _get_timestamp(self) -> str:
        """Get ISO format timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def format_answer_for_review(self, generated_answer: GeneratedAnswer) -> str:
        """
        Format answer for human review with full traceability
        
        Returns formatted string with answer, citations, and metadata
        """
        
        output = []
        output.append("=" * 80)
        output.append(f"QUESTION: {generated_answer.question}")
        output.append("=" * 80)
        output.append("")
        
        # Main answer
        output.append("ANSWER:")
        output.append(generated_answer.answer)
        output.append("")
        
        # Confidence and review flag
        output.append("-" * 80)
        output.append(f"CONFIDENCE SCORE: {generated_answer.confidence_score * 100:.0f}%")
        output.append(f"SUFFICIENT EVIDENCE: {'✅ Yes' if generated_answer.has_sufficient_evidence else '❌ No'}")
        output.append(f"REQUIRES MANUAL REVIEW: {'⚠️  Yes' if generated_answer.requires_manual_review else '✅ No'}")
        output.append("")
        
        # Citations
        if generated_answer.citations:
            output.append("CITATIONS:")
            for i, citation in enumerate(generated_answer.citations, 1):
                output.append(f"\n[{i}] {citation.source_file} (Chunk {citation.chunk_id})")
                output.append(f"    Similarity: {citation.similarity_score:.2f}")
                output.append(f"    Excerpt: {citation.excerpt}")
        else:
            output.append("CITATIONS: None - No documentation found")
        
        output.append("")
        output.append("-" * 80)
        output.append("")
        
        return "\n".join(output)
