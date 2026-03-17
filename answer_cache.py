"""
Answer Cache - Caches approved answers and reuses them for similar questions
Uses SQLite for persistent storage and semantic similarity matching
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CachedAnswer:
    """Represents a cached answer"""
    id: int
    original_question: str
    answer: str
    confidence_score: float
    source_file: str
    created_at: str
    reuse_count: int


class AnswerCache:
    """
    Manages answer caching and reuse with semantic similarity matching
    
    Features:
    - Persistent SQLite storage
    - Semantic similarity search
    - Configurable reuse threshold
    - Audit trail of reused answers
    """
    
    def __init__(self, db_path: str = "answer_cache.db", similarity_threshold: float = 0.85):
        """
        Initialize Answer Cache
        
        Args:
            db_path: Path to SQLite database file
            similarity_threshold: Minimum similarity score to trigger reuse (0-1)
        """
        self.db_path = Path(db_path)
        self.similarity_threshold = similarity_threshold
        self.rag_pipeline = None
        
        # Initialize database
        self._init_db()
    
    def set_rag_pipeline(self, rag_pipeline):
        """Set RAG pipeline for similarity calculations"""
        self.rag_pipeline = rag_pipeline
    
    def _init_db(self):
        """Initialize SQLite database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_question TEXT NOT NULL UNIQUE,
                answer TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reuse_count INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answer_reuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cached_answer_id INTEGER NOT NULL,
                reused_question TEXT NOT NULL,
                reused_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cached_answer_id) REFERENCES cached_answers(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Answer cache database initialized: {self.db_path}")
    
    def find_similar_answer(self, question: str) -> Optional[Tuple]:
        """
        Find a similar cached answer using semantic similarity
        
        Args:
            question: Question to search for
            
        Returns:
            Tuple of (CachedAnswer, similarity_score) if found above threshold, else None
        """
        if not self.rag_pipeline or not self.rag_pipeline.model:
            logger.warning("RAG pipeline not initialized. Cannot perform similarity search.")
            return None
        
        try:
            # Get all cached questions
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute('SELECT id, original_question, answer, confidence_score, source_file, created_at, reuse_count FROM cached_answers')
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            # Encode current question
            question_embedding = self.rag_pipeline.model.encode([question])[0]
            
            best_match = None
            best_similarity = 0.0
            
            # Compare with all cached questions
            for row in rows:
                cached_id, cached_question, answer, confidence, source, created, reuse_count = row
                
                # Encode cached question
                cached_embedding = self.rag_pipeline.model.encode([cached_question])[0]
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(question_embedding, cached_embedding)
                
                # Track best match
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (cached_id, cached_question, answer, confidence, source, created, reuse_count)
            
            # Return if above threshold
            if best_similarity >= self.similarity_threshold and best_match:
                cached_answer = CachedAnswer(
                    id=best_match[0],
                    original_question=best_match[1],
                    answer=best_match[2],
                    confidence_score=best_match[3],
                    source_file=best_match[4],
                    created_at=best_match[5],
                    reuse_count=best_match[6]
                )
                return (cached_answer, best_similarity)
            
            return None
        
        except Exception as e:
            logger.error(f"Error searching for similar answer: {e}")
            return None
    
    def cache_answer(self, question: str, answer: str, confidence_score: float, source_file: str = None) -> int:
        """
        Cache an approved answer
        
        Args:
            question: Original question
            answer: Generated answer
            confidence_score: Confidence score (0-1)
            source_file: Source questionnaire file
            
        Returns:
            ID of cached answer
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO cached_answers (original_question, answer, confidence_score, source_file)
                VALUES (?, ?, ?, ?)
            ''', (question, answer, confidence_score, source_file))
            
            answer_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Cached answer {answer_id} for question: {question[:50]}...")
            return answer_id
        
        except sqlite3.IntegrityError:
            logger.warning(f"Question already cached: {question[:50]}...")
            return None
        except Exception as e:
            logger.error(f"Error caching answer: {e}")
            return None
    
    def record_reuse(self, cached_answer_id: int, reused_question: str) -> bool:
        """
        Record that a cached answer was reused
        
        Args:
            cached_answer_id: ID of the cached answer
            reused_question: The new question that reused this answer
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Record the reuse
            cursor.execute('''
                INSERT INTO answer_reuses (cached_answer_id, reused_question)
                VALUES (?, ?)
            ''', (cached_answer_id, reused_question))
            
            # Increment reuse count
            cursor.execute('''
                UPDATE cached_answers SET reuse_count = reuse_count + 1
                WHERE id = ?
            ''', (cached_answer_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Recorded reuse of cached answer {cached_answer_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error recording reuse: {e}")
            return False
    
    def get_reuse_history(self, cached_answer_id: int) -> List[Tuple[str, str]]:
        """
        Get reuse history for a cached answer
        
        Args:
            cached_answer_id: ID of the cached answer
            
        Returns:
            List of (reused_question, reused_at) tuples
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT reused_question, reused_at FROM answer_reuses
                WHERE cached_answer_id = ?
                ORDER BY reused_at DESC
            ''', (cached_answer_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return rows
        
        except Exception as e:
            logger.error(f"Error fetching reuse history: {e}")
            return []
    
    def get_cache_stats(self) -> dict:
        """Get statistics about the answer cache"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Total cached answers
            cursor.execute('SELECT COUNT(*) FROM cached_answers')
            total_cached = cursor.fetchone()[0]
            
            # Total reuses
            cursor.execute('SELECT COUNT(*) FROM answer_reuses')
            total_reuses = cursor.fetchone()[0]
            
            # Average confidence
            cursor.execute('SELECT AVG(confidence_score) FROM cached_answers')
            avg_confidence = cursor.fetchone()[0] or 0
            
            # Most reused answer
            cursor.execute('''
                SELECT original_question, reuse_count FROM cached_answers
                ORDER BY reuse_count DESC LIMIT 1
            ''')
            most_reused = cursor.fetchone()
            
            conn.close()
            
            return {
                "total_cached_answers": total_cached,
                "total_reuses": total_reuses,
                "average_confidence": round(avg_confidence, 2),
                "most_reused_question": most_reused[0] if most_reused else None,
                "most_reused_count": most_reused[1] if most_reused else 0,
                "similarity_threshold": self.similarity_threshold
            }
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def clear_cache(self) -> bool:
        """Clear all cached answers"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM answer_reuses')
            cursor.execute('DELETE FROM cached_answers')
            
            conn.commit()
            conn.close()
            
            logger.info("Cleared answer cache")
            return True
        
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
