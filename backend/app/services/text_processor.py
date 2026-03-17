"""
Text processing service.
"""

from typing import List, Optional
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """Text processor utilities."""

    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """Extract and concatenate text from multiple files."""
        return FileParser.extract_from_multiple(file_paths)

    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Source text.
            chunk_size: Number of characters per chunk.
            overlap: Number of characters of overlap between consecutive chunks.

        Returns:
            List of text chunks.
        """
        return split_text_into_chunks(text, chunk_size, overlap)

    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Preprocess text:
        - Normalise line endings.
        - Remove excess blank lines.
        - Strip leading/trailing whitespace from each line.

        Args:
            text: Raw text.

        Returns:
            Preprocessed text.
        """
        import re

        # Normalise line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Collapse 3+ consecutive newlines to 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    @staticmethod
    def get_text_stats(text: str) -> dict:
        """Return basic statistics for the given text."""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }

