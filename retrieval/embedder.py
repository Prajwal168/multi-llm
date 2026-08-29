import os

from sentence_transformers import SentenceTransformer

class Embedder:
    """
    Generates embeddings for document chunks.

    You can configure the model with these environment variables:
    - EMBEDDER_MODEL_NAME: remote model id or local path
    - EMBEDDER_LOCAL_MODEL_PATH: local model directory to load directly
    """

    def __init__(self, model_name=None, local_model_path=None):

        model_name = model_name or os.getenv("EMBEDDER_MODEL_NAME", "all-MiniLM-L6-v2")
        local_model_path = local_model_path or os.getenv("EMBEDDER_LOCAL_MODEL_PATH")
        model_source = local_model_path or model_name

        try:
            self.model = SentenceTransformer(model_source)
        except Exception as exc:
            hint_lines = [
                "Failed to load the SentenceTransformer model.",
                f"Model source: {model_source}",
                "If you are offline, set EMBEDDER_LOCAL_MODEL_PATH to a local model directory.",
                "If you want to use the HuggingFace Hub, export HF_TOKEN for authenticated access.",
            ]
            message = "\n".join(hint_lines) + f"\nOriginal error: {exc}"
            raise RuntimeError(message) from exc

    def embed_chunks(self, chunks):

        """
        Embeds every chunk's content in a single batched `encode()`
        call instead of one call per chunk. Most embedding backends
        have meaningful fixed overhead per call, so this is
        significantly faster for large chunk sets while producing
        identical embeddings to the per-chunk version.
        """

        if not chunks:
            return []

        contents = [chunk["content"] for chunk in chunks]

        embeddings = self.model.encode(
            contents,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        embedded_chunks = []

        for chunk, embedding in zip(chunks, embeddings):

            embedded_chunk = chunk.copy()

            embedded_chunk["embedding"] = embedding.tolist()

            embedded_chunks.append(embedded_chunk)

        return embedded_chunks

if __name__ == "__main__":

    # Import Chunker using a package-relative import when executed as a module,
    # and fall back to a local import when the script is executed directly.
    try:
        from .chunker import Chunker
    except Exception:
        from chunker import Chunker

    chunker = Chunker()

    chunks = chunker.chunk_documents("documents")

    embedder = Embedder()

    embedded_chunks = embedder.embed_chunks(chunks)

    print(f"\nTotal Embedded Chunks: {len(embedded_chunks)}\n")

    first_chunk = embedded_chunks[0]

    print("Chunk ID :", first_chunk["chunk_id"])
    print("Domain   :", first_chunk["domain"])
    print("Source   :", first_chunk["source"])

    print("\nContent Preview:\n")
    print(first_chunk["content"][:250])

    print("\nEmbedding Dimension:")
    print(len(first_chunk["embedding"]))

    print("\nFirst 10 Values:")
    print(first_chunk["embedding"][:10])