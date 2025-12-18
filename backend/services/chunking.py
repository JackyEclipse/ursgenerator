"""
Chunking Service - Split documents into traceable chunks.

Features:
- Sentence/paragraph-aware splitting
- Overlap for context preservation
- Unique ID assignment for traceability
- Metadata preservation
"""

from typing import List, Optional, Tuple
from datetime import datetime
import hashlib
import re
import uuid

from models.ingest import SourceChunk, SourceType
from config import get_settings

settings = get_settings()


class ChunkingService:
    """
    Service for splitting documents into manageable, traceable chunks.
    """
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
    
    def chunk_text(
        self,
        text: str,
        source_id: str,
        source_type: SourceType,
        source_name: str,
        data_classification: str = "INTERNAL",
    ) -> List[SourceChunk]:
        """
        Split text into chunks with unique IDs.
        
        Uses sentence-aware splitting to avoid breaking mid-sentence.
        
        Args:
            text: The text to chunk
            source_id: Parent source document ID
            source_type: Type of source (document, email, etc.)
            source_name: Original filename or identifier
            data_classification: INTERNAL or CONFIDENTIAL
        
        Returns:
            List of SourceChunk objects
        """
        
        if not text or not text.strip():
            return []
        
        # Clean the text
        text = self._clean_text(text)
        
        # Split into sentences
        sentences = self._split_into_sentences(text)
        
        # Group sentences into chunks
        chunk_texts = self._group_into_chunks(sentences)
        
        # Create chunk objects
        chunks = []
        current_offset = 0
        
        for i, chunk_text in enumerate(chunk_texts):
            chunk_id = self._generate_chunk_id(source_id, i)
            content_hash = self._hash_content(chunk_text)
            
            chunk = SourceChunk(
                chunk_id=chunk_id,
                source_id=source_id,
                source_type=source_type,
                source_name=source_name,
                content=chunk_text,
                content_hash=content_hash,
                start_offset=current_offset,
                end_offset=current_offset + len(chunk_text),
                data_classification=data_classification,
                created_at=datetime.utcnow(),
            )
            
            chunks.append(chunk)
            current_offset += len(chunk_text)
        
        return chunks
    
    def chunk_document(
        self,
        pages: List[str],
        source_id: str,
        source_name: str,
        data_classification: str = "INTERNAL",
    ) -> List[SourceChunk]:
        """
        Chunk a multi-page document, preserving page numbers.
        
        Args:
            pages: List of text content, one per page
            source_id: Parent source document ID
            source_name: Original filename
            data_classification: INTERNAL or CONFIDENTIAL
        
        Returns:
            List of SourceChunk objects with page_number metadata
        """
        
        all_chunks = []
        chunk_index = 0
        
        for page_num, page_text in enumerate(pages, start=1):
            if not page_text or not page_text.strip():
                continue
            
            # Chunk this page
            sentences = self._split_into_sentences(page_text)
            chunk_texts = self._group_into_chunks(sentences)
            
            for chunk_text in chunk_texts:
                chunk_id = self._generate_chunk_id(source_id, chunk_index)
                
                chunk = SourceChunk(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    source_type=SourceType.DOCUMENT,
                    source_name=source_name,
                    content=chunk_text,
                    content_hash=self._hash_content(chunk_text),
                    page_number=page_num,
                    data_classification=data_classification,
                    created_at=datetime.utcnow(),
                )
                
                all_chunks.append(chunk)
                chunk_index += 1
        
        return all_chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        Uses simple heuristics - could be enhanced with NLP library.
        """
        # Split on sentence-ending punctuation followed by space and capital
        pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(pattern, text)
        
        # Also split on double newlines (paragraphs)
        result = []
        for sentence in sentences:
            if '\n\n' in sentence:
                result.extend(sentence.split('\n\n'))
            else:
                result.append(sentence)
        
        return [s.strip() for s in result if s.strip()]
    
    def _group_into_chunks(self, sentences: List[str]) -> List[str]:
        """
        Group sentences into chunks of approximately chunk_size characters.
        """
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence exceeds chunk size, start a new chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                
                # Keep overlap sentences
                overlap_text = ' '.join(current_chunk)
                if len(overlap_text) > self.chunk_overlap:
                    # Keep last few sentences for overlap
                    overlap_sentences = []
                    overlap_length = 0
                    for s in reversed(current_chunk):
                        if overlap_length + len(s) <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_length += len(s)
                        else:
                            break
                    current_chunk = overlap_sentences
                    current_length = overlap_length
                else:
                    current_chunk = []
                    current_length = 0
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _generate_chunk_id(self, source_id: str, index: int) -> str:
        """Generate a unique, deterministic chunk ID."""
        return f"{source_id}-chunk-{index:04d}"
    
    def _hash_content(self, content: str) -> str:
        """Generate a content hash for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def merge_chunks(
        self,
        chunk_ids: List[str],
        chunks_dict: dict,
    ) -> str:
        """
        Merge multiple chunks back into continuous text.
        Useful for providing context to LLM.
        """
        texts = []
        for chunk_id in chunk_ids:
            if chunk_id in chunks_dict:
                texts.append(chunks_dict[chunk_id].content)
        return '\n\n'.join(texts)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses simple heuristic - for accurate counts, use tiktoken.
        """
        # Rough estimate: 1 token ≈ 4 characters for English
        return len(text) // 4


# Singleton instance
_chunking_service: Optional[ChunkingService] = None


def get_chunking_service() -> ChunkingService:
    """Get or create the singleton chunking service instance."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service

