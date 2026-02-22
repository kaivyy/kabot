from pathlib import Path

from loguru import logger


class DocumentParser:
    """Utility class to read and extract text from various file formats."""

    @staticmethod
    def extract_text(file_path: str | Path) -> str:
        """Extract all text from a supported file type."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext == ".pdf":
            return DocumentParser._extract_from_pdf(path)
        elif ext in [".txt", ".md", ".csv"]:
            return DocumentParser._extract_from_text(path)
        else:
            raise ValueError(f"Unsupported file type for training: {ext}")

    @staticmethod
    def _extract_from_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required to parse PDFs. Run: pip install pypdf")

        logger.info(f"Extracting text from PDF: {path.name}")
        try:
            reader = PdfReader(str(path))
            text_blocks = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_blocks.append(text)
            return "\n\n".join(text_blocks)
        except Exception as e:
            logger.error(f"Failed to read PDF {path.name}: {e}")
            raise

    @staticmethod
    def _extract_from_text(path: Path) -> str:
        logger.info(f"Extracting text from plain text file: {path.name}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback for weird encodings
            with open(path, "r", encoding="latin-1") as f:
                return f.read()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Simple text chunker to divide large documents into memory-friendly blocks."""
        chunks = []
        if not text:
            return chunks

        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size

            # If not at the end of the string, try to find a natural break point (newline or period)
            if end < text_len:
                # Look backwards for a newline within the last 100 chars
                for search_offset in range(min(100, chunk_size)):
                    idx = end - search_offset
                    if idx > start and text[idx] in ["\n", "."]:
                        end = idx + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks
