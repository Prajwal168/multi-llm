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
    """

    def __init__(self,
                 db_path="vector_db",
                 collection_name="knowledge_base"):

        # Persistent database
        self.client = chromadb.PersistentClient(path=db_path)

        # Create the collection if it doesn't exist
        # or open the existing one.
        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )
    def add_documents(self, embedded_chunks):

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

        results = self.collection.query(

            query_embeddings=[query_embedding],

            n_results=top_k

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
            name=self.collection.name
        )
# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------




if __name__ == "__main__":

    store = VectorStore()

    print("Before Reset:", store.collection.count())

    store.reset_database()

    print("After Reset :", store.collection.count())