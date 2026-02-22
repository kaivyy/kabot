"""Vector store for semantic search using ChromaDB."""

from dataclasses import dataclass




@dataclass
class SearchResult:
    """Result from vector search."""
    id: str
    content: str


class VectorStore:
    """Vector store for semantic memory search."""

    def __init__(self, path: str = "./kabot_data", collection_name: str = "memory"):
        """
        Initialize vector store.

        Args:
            path: Path to store ChromaDB data
            collection_name: Name of the collection
        """
        import chromadb
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection_name)

    def add(self, documents: list[str], ids: list[str]):
        """
        Add documents to the vector store.

        Args:
            documents: List of document texts
            ids: List of document IDs
        """
        self.collection.upsert(
            documents=documents,
            ids=ids
        )

    def search(self, query: str, k: int = 3) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            List of search results
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )

        output = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i]
                output.append(SearchResult(id=doc_id, content=content))
        return output

    def delete(self, ids: list[str]):
        """Delete documents by IDs."""
        self.collection.delete(ids=ids)

    def clear(self):
        """Clear all documents from the collection."""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(self.collection.name)
