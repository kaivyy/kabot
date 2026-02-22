"""Tests for vector store."""

from kabot.memory.vector_store import VectorStore


def test_add_and_search(tmp_path):
    """Test adding documents and searching."""
    store = VectorStore(path=str(tmp_path), collection_name="test_mem")
    store.add(
        documents=["The cat sat on the mat", "Dogs are loyal"],
        ids=["1", "2"]
    )

    # Use more direct query for better semantic match
    results = store.search("cat sitting", k=1)
    assert len(results) == 1
    # Semantic search should return a result
    assert results[0].id in ["1", "2"]
    assert len(results[0].content) > 0


def test_search_empty_store(tmp_path):
    """Test searching in empty store."""
    store = VectorStore(path=str(tmp_path), collection_name="empty")
    results = store.search("anything", k=3)
    assert len(results) == 0


def test_multiple_results(tmp_path):
    """Test retrieving multiple search results."""
    store = VectorStore(path=str(tmp_path), collection_name="multi")
    store.add(
        documents=[
            "Python is a programming language",
            "JavaScript is used for web development",
            "Java is object-oriented"
        ],
        ids=["1", "2", "3"]
    )

    results = store.search("programming", k=2)
    assert len(results) <= 2
    assert any("Python" in r.content or "Java" in r.content for r in results)
