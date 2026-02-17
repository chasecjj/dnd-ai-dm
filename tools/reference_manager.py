"""
ReferenceManager — Search and retrieval over extracted PDF text + images.

Uses the pre-built indices from extract_references.py to find relevant
rules excerpts, lore, and visual assets at query time.
No API calls needed — all local keyword matching.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger('ReferenceManager')


class ReferenceManager:
    """Searches extracted PDF text and images for relevant D&D reference material."""
    
    # Book priority mapping: which books to search first for which agent
    RULES_BOOKS = [
        "player_s_handbook",
        "monster_manual",
        "xanathar_s_guide_to_everything",
        "mordenkainen_s_tome_of_foes",
    ]
    LORE_BOOKS = [
        "waterdeep_dragon_heist",
        "sword_coast_adventurer_s_guide",
        "volo_s_guide_to_monsters",
        "dungeon_master_s_guide",
    ]
    
    def __init__(self, extracted_dir: str = "knowledge/extracted", assets_dir: str = "knowledge/assets"):
        self.extracted_dir = os.path.abspath(extracted_dir)
        self.assets_dir = os.path.abspath(assets_dir)
        
        # Load indices
        self.text_index: List[Dict[str, Any]] = []
        self.asset_index: List[Dict[str, Any]] = []
        
        self._load_indices()
    
    def _load_indices(self):
        """Load the text and asset indices from JSON files."""
        text_index_path = os.path.join(self.extracted_dir, "index.json")
        asset_index_path = os.path.join(self.assets_dir, "index.json")
        
        if os.path.exists(text_index_path):
            with open(text_index_path, 'r', encoding='utf-8') as f:
                self.text_index = json.load(f)
            # Normalize Windows backslash paths to forward slashes for cross-platform support
            for chunk in self.text_index:
                if 'file' in chunk:
                    chunk['file'] = chunk['file'].replace('\\', '/')
            logger.info(f"Loaded text index: {len(self.text_index)} chunks")
        else:
            logger.warning(f"Text index not found: {text_index_path}")

        if os.path.exists(asset_index_path):
            with open(asset_index_path, 'r', encoding='utf-8') as f:
                self.asset_index = json.load(f)
            # Normalize Windows backslash paths to forward slashes for cross-platform support
            for asset in self.asset_index:
                if 'file' in asset:
                    asset['file'] = asset['file'].replace('\\', '/')
            logger.info(f"Loaded asset index: {len(self.asset_index)} images")
        else:
            logger.warning(f"Asset index not found: {asset_index_path}")
    
    # ------------------------------------------------------------------
    # Text Search
    # ------------------------------------------------------------------
    
    def search_rules(self, query: str, max_results: int = 3, max_tokens: int = 1000) -> str:
        """Search rules-focused books for relevant text.
        
        Args:
            query: The search query (e.g., "fireball", "troll stats", "grapple rules")
            max_results: Maximum number of chunks to return
            max_tokens: Approximate token budget (1 token ≈ 0.75 words)
        
        Returns:
            Formatted string of relevant excerpts for prompt injection.
        """
        return self._search_text(query, self.RULES_BOOKS, max_results, max_tokens)
    
    def search_lore(self, query: str, max_results: int = 3, max_tokens: int = 1000) -> str:
        """Search lore-focused books for relevant text.
        
        Args:
            query: The search query (e.g., "yawning portal", "zhentarim", "waterdeep wards")
            max_results: Maximum number of chunks to return
            max_tokens: Approximate token budget
        
        Returns:
            Formatted string of relevant excerpts for prompt injection.
        """
        return self._search_text(query, self.LORE_BOOKS, max_results, max_tokens)
    
    def search_all(self, query: str, max_results: int = 3, max_tokens: int = 1000) -> str:
        """Search all books for relevant text."""
        return self._search_text(query, None, max_results, max_tokens)
    
    def _search_text(self, query: str, book_filter: Optional[List[str]], 
                     max_results: int, max_tokens: int) -> str:
        """Core text search implementation.
        
        Scoring:
          - Keyword matches in the chunk's keyword list
          - Query term matches in the section name
          - Priority bonus for books in the preferred list
        """
        query_terms = self._tokenize_query(query)
        if not query_terms:
            return ""
        
        scored_chunks = []
        
        for chunk in self.text_index:
            # Filter by book if specified
            if book_filter and chunk.get('book_slug') not in book_filter:
                continue
            
            score = 0
            chunk_keywords = set(kw.lower() for kw in chunk.get('keywords', []))
            section_lower = chunk.get('section', '').lower()
            
            for term in query_terms:
                # Keyword match (strongest signal)
                if term in chunk_keywords:
                    score += 3
                # Partial keyword match
                elif any(term in kw for kw in chunk_keywords):
                    score += 1.5
                # Section name match
                if term in section_lower:
                    score += 2
            
            # Book priority bonus (earlier in list = higher priority)
            if book_filter:
                slug = chunk.get('book_slug', '')
                if slug in book_filter:
                    idx = book_filter.index(slug)
                    score += (len(book_filter) - idx) * 0.5
            
            if score > 0:
                scored_chunks.append((score, chunk))
        
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Build result string within token budget
        results = []
        total_words = 0
        max_words = int(max_tokens * 0.75)  # Rough token-to-word conversion
        
        for score, chunk in scored_chunks[:max_results * 2]:  # Check extra for budget
            if len(results) >= max_results:
                break
            
            # Read the actual chunk file
            chunk_text = self._read_chunk(chunk['file'])
            if not chunk_text:
                continue
            
            # Trim to fit budget
            chunk_words = len(chunk_text.split())
            if total_words + chunk_words > max_words:
                # Take a portion
                available = max_words - total_words
                if available < 50:
                    break
                words = chunk_text.split()[:available]
                chunk_text = ' '.join(words) + "..."
                chunk_words = available
            
            book = chunk.get('book', '?')
            pages = chunk.get('pages', '?')
            results.append(f"### [{book}, p.{pages}]\n{chunk_text}")
            total_words += chunk_words
        
        if not results:
            return ""
        
        return "\n\n---\n\n".join(results)
    
    def _read_chunk(self, relative_path: str) -> Optional[str]:
        """Read a text chunk file and return just the body (no frontmatter)."""
        full_path = os.path.join(self.extracted_dir, relative_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Strip YAML frontmatter
            if content.startswith('---'):
                end_idx = content.find('---', 3)
                if end_idx != -1:
                    content = content[end_idx + 3:].strip()
            
            # Strip page markers for cleaner output
            content = re.sub(r'--- Page \d+ ---', '', content)
            
            return content.strip()
        except Exception as e:
            logger.error(f"Error reading chunk {full_path}: {e}")
            return None
    
    # ------------------------------------------------------------------
    # Asset Search
    # ------------------------------------------------------------------
    
    def find_asset(self, query: str, max_results: int = 1) -> List[Dict[str, Any]]:
        """Search for relevant images/maps.
        
        Args:
            query: What to search for (e.g., "troll", "yawning portal map")
            max_results: Maximum number of images to return
        
        Returns:
            List of dicts with 'file' (absolute path), 'page', 'book_slug', 'context'
        """
        query_terms = self._tokenize_query(query)
        if not query_terms:
            return []
        
        scored = []
        
        for asset in self.asset_index:
            score = 0
            context_lower = asset.get('context', '').lower()
            
            for term in query_terms:
                if term in context_lower:
                    score += 2
            
            # Prefer larger images (more likely to be maps/illustrations vs thumbnails)
            size = asset.get('size_bytes', 0)
            if size > 500_000:  # > 500KB
                score += 1
            if size > 1_000_000:  # > 1MB
                score += 1
            
            if score > 0:
                scored.append((score, asset))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for _, asset in scored[:max_results]:
            results.append({
                'file': os.path.join(self.assets_dir, asset['file']),
                'page': asset.get('page', '?'),
                'book_slug': asset.get('book_slug', '?'),
                'context': asset.get('context', '')[:100],
                'size_bytes': asset.get('size_bytes', 0),
                'width': asset.get('width', 0),
                'height': asset.get('height', 0),
            })
        
        return results
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    @staticmethod
    def _tokenize_query(query: str) -> List[str]:
        """Break a query into searchable terms."""
        # Split on whitespace and punctuation, lowercase, filter short words
        terms = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        # Remove very common English words
        stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
                     'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has',
                     'that', 'this', 'with', 'what', 'from', 'they', 'been',
                     'make', 'like', 'does', 'how', 'their', 'about'}
        return [t for t in terms if t not in stopwords]
    
    def get_stats(self) -> Dict[str, int]:
        """Return stats about the loaded indices."""
        return {
            'text_chunks': len(self.text_index),
            'images': len(self.asset_index),
            'books': len(set(c.get('book_slug', '') for c in self.text_index))
        }
