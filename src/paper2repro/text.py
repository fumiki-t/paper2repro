"""Conservative text normalization shared by evidence validators."""

import re
import unicodedata


_LINE_BREAK_HYPHENATION = re.compile(
    r"(?<=[^\W\d_])[-\u2010]\s*\n\s*(?=[^\W\d_])"
)


def normalize_extracted_text(text: str) -> str:
    """Normalize common PDF/text extraction artifacts without fuzzy matching."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = _LINE_BREAK_HYPHENATION.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_normalized_excerpt(content: str, excerpt: str) -> bool:
    """Anchor an excerpt using normalized then whitespace-free substrings."""
    normalized_content = normalize_extracted_text(content)
    normalized_excerpt = normalize_extracted_text(excerpt)
    if not normalized_excerpt:
        return False
    if normalized_excerpt in normalized_content:
        return True
    compact_content = re.sub(r"\s+", "", normalized_content)
    compact_excerpt = re.sub(r"\s+", "", normalized_excerpt)
    return compact_excerpt in compact_content
