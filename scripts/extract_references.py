"""
extract_references.py — One-time script to extract text + images from D&D PDFs.

Outputs:
  knowledge/extracted/{book_slug}/chunk_{NNN}.md   (text chunks with YAML frontmatter)
  knowledge/extracted/index.json                   (keyword → chunk path mapping)
  knowledge/assets/{book_slug}/page_{N}_img_{M}.png (images ≥ 50KB)
  knowledge/assets/index.json                      (image metadata index)

Usage:
  python scripts/extract_references.py
"""

import os
import re
import json
import sys
import hashlib
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REFERENCES_DIR = os.path.join("knowledge", "References")
EXTRACTED_DIR = os.path.join("knowledge", "extracted")
ASSETS_DIR = os.path.join("knowledge", "assets")

# Only process these PDFs (skip character sheets, blank sheets)
TARGET_PDFS = [
    "D&D 5E - Player's Handbook.pdf",
    "D&D 5E - Dungeon Master's Guide.pdf",
    "D&D 5E - Monster Manual.pdf",
    "D&D 5E - Waterdeep - Dragon Heist.pdf",
    "D&D 5E - Sword Coast Adventurer's Guide.pdf",
    "D&D 5E - Volo's Guide to Monsters.pdf",
    "D&D 5E - Xanathar's Guide to Everything.pdf",
    "D&D 5E - Mordenkainen's Tome of Foes.pdf",
]

# Minimum image size to extract (filters decorative borders, tiny icons)
MIN_IMAGE_BYTES = 50_000  # 50 KB

# Target chunk size in words (roughly 500 words ≈ 650 tokens)
CHUNK_TARGET_WORDS = 500


def slugify(name: str) -> str:
    """Convert a PDF filename into a directory-safe slug."""
    # Remove "D&D 5E - " prefix and ".pdf" suffix
    slug = name.replace("D&D 5E - ", "").replace(".pdf", "")
    # Replace special chars
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', slug).strip('_').lower()
    return slug


def extract_keywords(text: str) -> list:
    """Extract meaningful keywords from text for the search index."""
    # Common D&D terms we want to capture
    text_lower = text.lower()
    
    # Extract capitalized multi-word terms (spell names, creature names, locations)
    proper_nouns = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text)
    
    # Extract words that appear in headers or bold text
    header_words = re.findall(r'#+\s+(.+)', text)
    
    # Common keywords: just use unique words ≥ 4 chars, lowercased
    words = set()
    for word in re.findall(r'\b[a-zA-Z]{4,}\b', text_lower):
        words.add(word)
    
    # Combine and deduplicate
    keywords = set()
    for pn in proper_nouns:
        keywords.add(pn.lower().strip())
    for hw in header_words:
        for w in hw.split():
            if len(w) >= 3:
                keywords.add(w.lower().strip())
    keywords.update(list(words)[:30])  # Cap generic words
    
    return sorted(list(keywords))[:50]  # Max 50 keywords per chunk


def detect_section_header(line: str) -> bool:
    """Check if a line looks like a section header (ALL CAPS, short, or numbered)."""
    stripped = line.strip()
    if not stripped:
        return False
    # All caps and short (chapter/section titles)
    if stripped.isupper() and len(stripped) < 80 and len(stripped) > 3:
        return True
    # Chapter N: or Part N:
    if re.match(r'^(Chapter|Part|Appendix|Section)\s+\d', stripped, re.IGNORECASE):
        return True
    return False


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str, book_slug: str, book_name: str):
    """Extract text from a PDF, chunk it, and save as markdown files.
    
    Returns list of chunk metadata dicts for the master index.
    """
    output_dir = os.path.join(EXTRACTED_DIR, book_slug)
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"  📖 {total_pages} pages")
    
    chunks = []
    current_chunk_text = ""
    current_chunk_pages = []
    current_section = "Introduction"
    chunk_index = 0
    
    for page_num in range(total_pages):
        try:
            page = doc[page_num]
            text = page.get_text("text")
        except Exception as e:
            print(f"  ⚠️  Page {page_num + 1}: extraction error ({e})")
            continue
        
        if not text or len(text.strip()) < 20:
            continue
        
        # Check for section headers
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines of page
            if detect_section_header(line):
                current_section = line.strip().title()
                break
        
        current_chunk_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"
        current_chunk_pages.append(page_num + 1)
        
        # Check if chunk is large enough to save
        word_count = len(current_chunk_text.split())
        if word_count >= CHUNK_TARGET_WORDS:
            chunk_meta = _save_chunk(
                output_dir, book_name, book_slug,
                chunk_index, current_chunk_text,
                current_chunk_pages, current_section
            )
            chunks.append(chunk_meta)
            chunk_index += 1
            current_chunk_text = ""
            current_chunk_pages = []
    
    # Save any remaining text
    if current_chunk_text.strip():
        chunk_meta = _save_chunk(
            output_dir, book_name, book_slug,
            chunk_index, current_chunk_text,
            current_chunk_pages, current_section
        )
        chunks.append(chunk_meta)
    
    doc.close()
    print(f"  ✅ {len(chunks)} text chunks extracted")
    return chunks


def _save_chunk(output_dir, book_name, book_slug, index, text, pages, section):
    """Save a text chunk as a markdown file with YAML frontmatter."""
    keywords = extract_keywords(text)
    page_range = f"{pages[0]}-{pages[-1]}" if pages else "?"
    
    frontmatter = (
        f"---\n"
        f"book: \"{book_name}\"\n"
        f"book_slug: \"{book_slug}\"\n"
        f"pages: \"{page_range}\"\n"
        f"section: \"{section}\"\n"
        f"keywords: {json.dumps(keywords[:20])}\n"
        f"---\n"
    )
    
    filename = f"chunk_{index:04d}.md"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + text)
    
    return {
        "file": os.path.join(book_slug, filename),
        "book": book_name,
        "book_slug": book_slug,
        "pages": page_range,
        "section": section,
        "keywords": keywords,
        "word_count": len(text.split())
    }


# ---------------------------------------------------------------------------
# Image Extraction
# ---------------------------------------------------------------------------

def extract_images_from_pdf(pdf_path: str, book_slug: str):
    """Extract images from a PDF and save as PNG files.
    
    Returns list of image metadata dicts for the asset index.
    """
    output_dir = os.path.join(ASSETS_DIR, book_slug)
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    images = []
    seen_hashes = set()  # Deduplicate identical images
    extracted = 0
    skipped_small = 0
    skipped_dup = 0
    
    for page_num in range(total_pages):
        try:
            page = doc[page_num]
            image_list = page.get_images(full=True)
        except Exception:
            continue
        
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue
                
                image_bytes = base_image["image"]
                
                # Filter tiny images
                if len(image_bytes) < MIN_IMAGE_BYTES:
                    skipped_small += 1
                    continue
                
                # Deduplicate
                img_hash = hashlib.md5(image_bytes).hexdigest()
                if img_hash in seen_hashes:
                    skipped_dup += 1
                    continue
                seen_hashes.add(img_hash)
                
                # Determine extension
                ext = base_image.get("ext", "png")
                if ext not in ("png", "jpg", "jpeg"):
                    ext = "png"
                
                filename = f"page_{page_num + 1:04d}_img_{img_idx}.{ext}"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                
                # Get page text for context
                try:
                    page_text = page.get_text("text")[:200]
                except Exception:
                    page_text = ""
                
                images.append({
                    "file": os.path.join(book_slug, filename),
                    "book_slug": book_slug,
                    "page": page_num + 1,
                    "size_bytes": len(image_bytes),
                    "width": base_image.get("width", 0),
                    "height": base_image.get("height", 0),
                    "context": page_text.replace('\n', ' ').strip()
                })
                extracted += 1
                
            except Exception as e:
                continue
    
    doc.close()
    print(f"  🖼️  {extracted} images extracted, {skipped_small} too small, {skipped_dup} duplicates")
    return images


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("D&D Reference Extraction Script")
    print("=" * 60)
    
    # Verify references directory
    if not os.path.isdir(REFERENCES_DIR):
        print(f"ERROR: References directory not found: {REFERENCES_DIR}")
        sys.exit(1)
    
    # Create output directories
    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    all_text_chunks = []
    all_images = []
    
    for pdf_name in TARGET_PDFS:
        pdf_path = os.path.join(REFERENCES_DIR, pdf_name)
        
        if not os.path.exists(pdf_path):
            print(f"\n⚠️  SKIPPING (not found): {pdf_name}")
            continue
        
        book_slug = slugify(pdf_name)
        book_name = pdf_name.replace("D&D 5E - ", "").replace(".pdf", "")
        
        print(f"\n📚 Processing: {book_name}")
        print(f"   Slug: {book_slug}")
        
        # Extract text
        print("  Extracting text...")
        text_chunks = extract_text_from_pdf(pdf_path, book_slug, book_name)
        all_text_chunks.extend(text_chunks)
        
        # Extract images
        print("  Extracting images...")
        images = extract_images_from_pdf(pdf_path, book_slug)
        all_images.extend(images)
    
    # Write text index
    text_index_path = os.path.join(EXTRACTED_DIR, "index.json")
    with open(text_index_path, 'w', encoding='utf-8') as f:
        json.dump(all_text_chunks, f, indent=2, ensure_ascii=False)
    
    # Write asset index
    asset_index_path = os.path.join(ASSETS_DIR, "index.json")
    with open(asset_index_path, 'w', encoding='utf-8') as f:
        json.dump(all_images, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Text chunks: {len(all_text_chunks)} (in {EXTRACTED_DIR}/)")
    print(f"  Images:      {len(all_images)} (in {ASSETS_DIR}/)")
    print(f"  Text index:  {text_index_path}")
    print(f"  Asset index: {asset_index_path}")
    
    # Stats per book
    books = {}
    for chunk in all_text_chunks:
        slug = chunk['book_slug']
        books.setdefault(slug, {'chunks': 0, 'images': 0})
        books[slug]['chunks'] += 1
    for img in all_images:
        slug = img['book_slug']
        books.setdefault(slug, {'chunks': 0, 'images': 0})
        books[slug]['images'] += 1
    
    print("\n  Per-book breakdown:")
    for slug, counts in sorted(books.items()):
        print(f"    {slug}: {counts['chunks']} chunks, {counts['images']} images")


if __name__ == "__main__":
    main()
