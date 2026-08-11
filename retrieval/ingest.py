from pathlib import Path
import sys

# Allow direct execution:
# python retrieval/ingest.py
sys.path.append(str(Path(__file__).resolve().parent))

from chunker import Chunker
from embedder import Embedder
from vector_store import VectorStore


class IngestionPipeline:
    """
    Rebuilds the Vector Database from the documents
    currently present in the documents/ directory.
    """

    def __init__(self, documents_path="documents"):

        self.documents_path = documents_path

        self.chunker = Chunker()

        self.embedder = Embedder()

        self.vector_store = VectorStore()

    def run(self):

        print("\nStarting ingestion...\n")

        # ---------------------------------------------
        # 1. Reset existing Vector DB
        # ---------------------------------------------

        print("Resetting Vector Database...")

        self.vector_store.reset_database()

        print("Vector Database reset.\n")

        # ---------------------------------------------
        # 2. Chunk documents
        # ---------------------------------------------

        print("Chunking documents...")

        chunks = self.chunker.chunk_documents(
            self.documents_path
        )

        print(f"Chunks created: {len(chunks)}\n")

        if not chunks:
            print("No supported documents found.")
            return

        # ---------------------------------------------
        # 3. Generate embeddings
        # ---------------------------------------------

        print("Generating embeddings...")

        embedded_chunks = self.embedder.embed_chunks(
            chunks
        )

        print(
            f"Embeddings generated: "
            f"{len(embedded_chunks)}\n"
        )

        # ---------------------------------------------
        # 4. Store in Vector DB
        # ---------------------------------------------

        print("Storing embeddings in ChromaDB...")

        self.vector_store.add_documents(
            embedded_chunks
        )

        print("Documents stored successfully.\n")

        # ---------------------------------------------
        # 5. Final status
        # ---------------------------------------------

        print("=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)

        print(
            f"Documents indexed: "
            f"{self.vector_store.collection.count()}"
        )


# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------

if __name__ == "__main__":

    pipeline = IngestionPipeline()

    pipeline.run()