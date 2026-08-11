from pathlib import Path
import sys

# Allow the file to be run directly:
# python retrieval/chunker.py
sys.path.append(str(Path(__file__).resolve().parent))

from document_loader import DocumentLoader


class Chunker:
    """
    Splits documents into structure-aware chunks.

    The chunker:
    - Supports Markdown and PDF files through DocumentLoader.
    - Preserves paragraph boundaries.
    - Attempts to keep related text together.
    - Avoids cutting words in the middle.
    - Maintains chunk metadata.
    """

    def __init__(self, chunk_size=1000, overlap=200):

        self.chunk_size = chunk_size
        self.overlap = overlap

        self.loader = DocumentLoader()

    def chunk_documents(self, documents_path):

        chunks = []

        documents_path = Path(documents_path)

        chunk_id = 1

        supported_extensions = {".md", ".pdf"}

        for file in documents_path.rglob("*"):

            if file.suffix.lower() not in supported_extensions:
                continue

            text = self.loader.load(file)

            if not text.strip():
                continue

            domain = file.parent.name

            document_chunks = self._chunk_text(text)

            for content in document_chunks:

                chunks.append({

                    "chunk_id": chunk_id,

                    "domain": domain,

                    "source": str(file),

                    "content": content

                })

                chunk_id += 1

        return chunks

    def _chunk_text(self, text):

        # Normalize line endings
        text = text.replace("\r\n", "\n")

        # Split based on blank lines.
        paragraphs = [
            paragraph.strip()
            for paragraph in text.split("\n\n")
            if paragraph.strip()
        ]

        chunks = []

        current_parts = []
        current_length = 0

        for paragraph in paragraphs:

            paragraph_length = len(paragraph)

            # If adding this paragraph exceeds the target size,
            # finalize the current chunk.
            if (
                current_parts
                and current_length + paragraph_length + 2
                > self.chunk_size
            ):

                chunk = "\n\n".join(current_parts)

                chunks.append(chunk)

                # Keep the last part as overlap.
                overlap_parts = []
                overlap_length = 0

                for part in reversed(current_parts):

                    if overlap_length + len(part) > self.overlap:
                        break

                    overlap_parts.insert(0, part)

                    overlap_length += len(part) + 2

                current_parts = overlap_parts

                current_length = overlap_length

            # Handle a paragraph larger than chunk_size.
            if paragraph_length > self.chunk_size:

                if current_parts:

                    chunks.append("\n\n".join(current_parts))

                    current_parts = []
                    current_length = 0

                large_chunks = self._split_large_paragraph(
                    paragraph
                )

                chunks.extend(large_chunks)

            else:

                current_parts.append(paragraph)

                current_length += paragraph_length + 2

        # Add remaining content.
        if current_parts:

            chunks.append("\n\n".join(current_parts))

        return chunks

    def _split_large_paragraph(self, text):

        """
        Handles a single paragraph that is larger than
        the target chunk size.

        Splits at sentence boundaries where possible.
        """

        sentences = self._split_sentences(text)

        chunks = []

        current = []
        current_length = 0

        for sentence in sentences:

            sentence_length = len(sentence)

            if (
                current
                and current_length + sentence_length + 1
                > self.chunk_size
            ):

                chunks.append(" ".join(current))

                current = []
                current_length = 0

            current.append(sentence)

            current_length += sentence_length + 1

        if current:

            chunks.append(" ".join(current))

        return chunks

    def _split_sentences(self, text):

        """
        Simple sentence splitting.

        Keeps the implementation lightweight and
        avoids introducing another NLP dependency.
        """

        import re

        sentences = re.split(
            r"(?<=[.!?])\s+",
            text
        )

        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]


# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------

if __name__ == "__main__":

    chunker = Chunker(
        chunk_size=1000,
        overlap=200
    )

    chunks = chunker.chunk_documents("documents")

    print(f"\nTotal Chunks: {len(chunks)}\n")

    for chunk in chunks[:10]:

        print(f"Chunk ID : {chunk['chunk_id']}")
        print(f"Domain   : {chunk['domain']}")
        print(f"Source   : {chunk['source']}")
        print(f"Characters: {len(chunk['content'])}")

        print("\nContent Preview:")
        print(chunk["content"][:500])

        print("-" * 80)