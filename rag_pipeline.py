"""
RAG Pipeline - Retrieval-Augmented Generation for Compliance Documents
Ingests security documentation, generates embeddings, and retrieves relevant chunks
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
from dataclasses import dataclass, asdict

# Try to import optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of a document with metadata"""
    content: str
    source: str
    chunk_id: int
    start_char: int
    end_char: int
    embedding: List[float] = None


class RAGPipeline:
    """
    Retrieval-Augmented Generation Pipeline for compliance documents
    
    Features:
    - Document ingestion from multiple file types (PDF, TXT, DOCX)
    - Intelligent chunking with overlap
    - Embedding generation using sentence-transformers
    - Vector similarity search with FAISS
    - Persistent storage of embeddings
    """
    
    def __init__(self, vector_db_path: str = "vector_db", 
                 model_name: str = "all-MiniLM-L6-v2",
                 chunk_size: int = 500,
                 chunk_overlap: int = 100):
        """
        Initialize RAG Pipeline
        
        Args:
            vector_db_path: Path to store vector database
            model_name: Sentence transformer model to use
            chunk_size: Size of document chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.vector_db_path = Path(vector_db_path)
        self.vector_db_path.mkdir(exist_ok=True)
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: List[DocumentChunk] = []
        self.embeddings_index = None
        self.model = None
        
        # Initialize embedding model
        if HAS_SENTENCE_TRANSFORMERS:
            logger.info(f"Loading embedding model: {model_name}")
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
        else:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
            self.embedding_dim = 384  # Default dimension for all-MiniLM-L6-v2
        
        # Try to load existing index
        self._load_index()
    
    def ingest_documents(self, doc_paths: List[str]) -> int:
        """
        Ingest documents from file paths
        
        Args:
            doc_paths: List of file paths to ingest
            
        Returns:
            Number of chunks created
        """
        total_chunks_before = len(self.chunks)
        
        for doc_path in doc_paths:
            path = Path(doc_path)
            if not path.exists():
                logger.warning(f"File not found: {doc_path}")
                continue
            
            logger.info(f"Ingesting: {path.name}")
            
            # Read document based on file type
            if path.suffix.lower() == '.txt':
                content = self._read_txt(path)
            elif path.suffix.lower() == '.pdf':
                content = self._read_pdf(path)
            elif path.suffix.lower() == '.docx':
                content = self._read_docx(path)
            else:
                logger.warning(f"Unsupported file type: {path.suffix}")
                continue
            
            # Create chunks
            chunks = self._chunk_document(content, str(path))
            self.chunks.extend(chunks)
            logger.info(f"Created {len(chunks)} chunks from {path.name}")
        
        # Generate embeddings for new chunks
        if len(self.chunks) > total_chunks_before:
            self._generate_embeddings()
            self._build_faiss_index()
            self._save_index()
        
        return len(self.chunks) - total_chunks_before
    
    def retrieve_relevant_chunks(self, query: str, top_k: int = 5) -> List[DocumentChunk]:
        """
        Retrieve most relevant chunks for a query
        
        Args:
            query: Query text
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of relevant DocumentChunk objects
        """
        if not self.model or not self.embeddings_index:
            logger.warning("RAG pipeline not initialized. No chunks indexed.")
            return []
        
        # Generate query embedding
        query_embedding = self.model.encode([query])[0]
        query_embedding = np.array([query_embedding]).astype('float32')
        
        # Search index
        distances, indices = self.embeddings_index.search(query_embedding, min(top_k, len(self.chunks)))
        
        # Return chunks with similarity scores
        relevant_chunks = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                # Store similarity score (lower distance = higher similarity)
                chunk.similarity_score = float(1 / (1 + distance))
                relevant_chunks.append(chunk)
        
        return relevant_chunks
    
    def get_context_for_question(self, question: str, max_tokens: int = 2000) -> str:
        """
        Get formatted context for a question
        
        Args:
            question: Question to answer
            max_tokens: Maximum tokens in context (approximate)
            
        Returns:
            Formatted context string for Claude
        """
        relevant_chunks = self.retrieve_relevant_chunks(question, top_k=10)
        
        context_parts = []
        token_count = 0
        
        for chunk in relevant_chunks:
            chunk_text = f"[From {Path(chunk.source).name}]\n{chunk.content}\n"
            # Rough token estimate (1 token ≈ 4 characters)
            chunk_tokens = len(chunk_text) // 4
            
            if token_count + chunk_tokens <= max_tokens:
                context_parts.append(chunk_text)
                token_count += chunk_tokens
            else:
                break
        
        if not context_parts:
            logger.warning(f"No relevant chunks found for question: {question}")
            return "No relevant compliance documentation found."
        
        return "\n---\n".join(context_parts)
    
    def _chunk_document(self, content: str, source: str) -> List[DocumentChunk]:
        """Split document into overlapping chunks"""
        chunks = []
        chunk_id = len(self.chunks)
        
        for i in range(0, len(content), self.chunk_size - self.chunk_overlap):
            chunk_content = content[i:i + self.chunk_size]
            
            if len(chunk_content.strip()) > 50:  # Skip very small chunks
                chunk = DocumentChunk(
                    content=chunk_content,
                    source=source,
                    chunk_id=chunk_id,
                    start_char=i,
                    end_char=min(i + self.chunk_size, len(content))
                )
                chunks.append(chunk)
                chunk_id += 1
        
        return chunks
    
    def _generate_embeddings(self):
        """Generate embeddings for all chunks"""
        if not self.model:
            logger.error("Embedding model not available")
            return
        
        logger.info(f"Generating embeddings for {len(self.chunks)} chunks...")
        
        # Get texts for chunks that don't have embeddings
        texts_to_embed = []
        indices_to_embed = []
        
        for i, chunk in enumerate(self.chunks):
            if chunk.embedding is None:
                texts_to_embed.append(chunk.content)
                indices_to_embed.append(i)
        
        if texts_to_embed:
            embeddings = self.model.encode(texts_to_embed, show_progress_bar=True)
            
            for idx, embedding in zip(indices_to_embed, embeddings):
                self.chunks[idx].embedding = embedding.tolist()
    
    def _build_faiss_index(self):
        """Build FAISS index for similarity search"""
        if not HAS_FAISS:
            logger.warning("FAISS not installed. Install with: pip install faiss-cpu")
            return
        
        logger.info("Building FAISS index...")
        
        embeddings = np.array([
            chunk.embedding if chunk.embedding else np.zeros(self.embedding_dim)
            for chunk in self.chunks
        ]).astype('float32')
        
        self.embeddings_index = faiss.IndexFlatL2(self.embedding_dim)
        self.embeddings_index.add(embeddings)
    
    def _save_index(self):
        """Save chunks and index to disk"""
        # Save chunks metadata
        chunks_data = []
        for chunk in self.chunks:
            chunk_dict = asdict(chunk)
            chunks_data.append(chunk_dict)
        
        chunks_file = self.vector_db_path / "chunks.json"
        with open(chunks_file, 'w') as f:
            json.dump(chunks_data, f, indent=2)
        
        # Save FAISS index
        if self.embeddings_index and HAS_FAISS:
            index_file = self.vector_db_path / "index.faiss"
            faiss.write_index(self.embeddings_index, str(index_file))
        
        logger.info(f"Saved {len(self.chunks)} chunks to {self.vector_db_path}")
    
    def _load_index(self):
        """Load chunks and index from disk"""
        chunks_file = self.vector_db_path / "chunks.json"
        index_file = self.vector_db_path / "index.faiss"
        
        if chunks_file.exists():
            try:
                with open(chunks_file, 'r') as f:
                    chunks_data = json.load(f)
                
                self.chunks = [
                    DocumentChunk(**chunk_dict) for chunk_dict in chunks_data
                ]
                logger.info(f"Loaded {len(self.chunks)} chunks from disk")
                
                # Load FAISS index
                if index_file.exists() and HAS_FAISS:
                    self.embeddings_index = faiss.read_index(str(index_file))
                    logger.info("Loaded FAISS index from disk")
            
            except Exception as e:
                logger.error(f"Error loading index: {e}")
    
    def _read_txt(self, path: Path) -> str:
        """Read text file"""
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _read_pdf(self, path: Path) -> str:
        """Read PDF file"""
        try:
            import PyPDF2
            text = []
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
            return '\n'.join(text)
        except ImportError:
            logger.warning("PyPDF2 not installed. Install with: pip install PyPDF2")
            return ""
    
    def _read_docx(self, path: Path) -> str:
        """Read DOCX file"""
        try:
            from docx import Document
            doc = Document(path)
            return '\n'.join([para.text for para in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx not installed. Install with: pip install python-docx")
            return ""
    
    def clear_index(self):
        """Clear all indexed documents"""
        self.chunks = []
        self.embeddings_index = None
        logger.info("Cleared RAG index")
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG pipeline"""
        return {
            "total_chunks": len(self.chunks),
            "total_documents": len(set(chunk.source for chunk in self.chunks)),
            "embedding_model": "all-MiniLM-L6-v2" if self.model else "None",
            "embedding_dimension": self.embedding_dim,
            "index_built": self.embeddings_index is not None,
            "vector_db_path": str(self.vector_db_path)
        }


# Convenience function for quick usage
def create_rag_pipeline(doc_paths: List[str]) -> RAGPipeline:
    """Create and initialize RAG pipeline with documents"""
    pipeline = RAGPipeline()
    pipeline.ingest_documents(doc_paths)
    return pipeline
