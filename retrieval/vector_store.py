import os
import chromadb


class VectorStore:
    """
    Wrapper around ChromaDB.

    Responsibilities:
    - Initialize the database
    - Create/Open a collection
    - (Later) Add documents
    - (Later) Search documents

    Changes vs. the original version:
      1. `search` clamps `top_k` to the collection's actual document
         count and returns [] immediately for an empty collection,
         instead of letting Chroma raise when more results are
         requested than exist (easy to hit with a small/test corpus,
         or a caller that over-fetches for dedup purposes).
      2. `add_documents` is a no-op (with a message) when given an
         empty list, instead of calling `collection.add` with all
         empty lists.
    """

    def __init__(self,
                 db_path="vector_db",
                 collection_name="knowledge_base"):

        self.collection_name = collection_name

        # Persistent database
        self.client = chromadb.PersistentClient(path=db_path)

        # Create the collection if it doesn't exist
        # or open the existing one.
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    def add_documents(self, embedded_chunks):

        if not embedded_chunks:
            print("No embedded chunks to add; skipping.")
            return

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in embedded_chunks:

            ids.append(str(chunk["chunk_id"]))

            documents.append(chunk["content"])

            embeddings.append(chunk["embedding"])

            metadatas.append({

                "domain": chunk["domain"],

                "source": chunk["source"]

            })

        self.collection.add(

            ids=ids,

            documents=documents,

            embeddings=embeddings,

            metadatas=metadatas

        )
    def search(self, query_embedding, top_k=5):

        # Chroma errors if you ask for more results than the
        # collection contains (e.g. a small/test corpus, or an
        # over-fetching caller like StaticRetriever's dedup logic
        # requesting top_k * 3). Clamp instead of letting that
        # surface as a confusing runtime error, and short-circuit
        # an empty collection entirely.
        available = self.collection.count()

        if available == 0:
            return []

        effective_top_k = min(top_k, available)

        results = self.collection.query(

            query_embeddings=[query_embedding],

            n_results=effective_top_k

        )

        retrieved_chunks = []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for document, metadata, distance in zip(
                documents,
                metadatas,
                distances
        ):

            retrieved_chunks.append({

                "content": document,

                "domain": metadata["domain"],

                "source": metadata["source"],

                "score": distance

            })

        return retrieved_chunks

    def reset_database(self):

        # Delete the existing collection
        self.client.delete_collection(
            name=self.collection.name
        )

        # Recreate an empty collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
# --------------------------------------------------
# Standalone Testing
# ------------------------------------------------




if __name__ == "__main__":

    store = VectorStore()

    print("Before Reset:", store.collection.count())

    store.reset_database()

    print("After Reset :", store.collection.count())