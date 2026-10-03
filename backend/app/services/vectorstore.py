"""Vector store service interface and implementations.

Abstracts vector storage, indexing, and similarity retrieval,
making it easy to swap ChromaDB with Pinecone, Qdrant, Milvus, or FAISS.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """Abstract base interface for vector database operations."""

    @abstractmethod
    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """Store chunk dictionaries and their embeddings into the vector database.

        Args:
            chunks: List of chunk dicts containing 'chunk_id', 'text', and 'metadata'.
            embeddings: Optional precomputed list of embedding vectors.
        """
        pass

    @abstractmethod
    def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        """Store chunk texts, embeddings, and metadata in the vector database."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Retrieve the top-k most similar document chunks for a query embedding.

        Args:
            query_embedding: The query vector.
            top_k: Number of nearest neighbors to retrieve.

        Returns:
            List of matching records with text, metadata, and distance score.
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search with optional doc_id filter and structured output.

        Args:
            query_embedding: The query vector.
            top_k: Number of nearest neighbors to retrieve.
            doc_ids: Optional list of document IDs to restrict search to.

        Returns:
            List of dicts with keys: text, filename, page, score, chunk_id.
        """
        pass

    @abstractmethod
    def delete_collection(self) -> None:
        """Clear or reset the vector store collection."""
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document.

        Args:
            doc_id: The document ID whose chunks should be deleted.

        Returns:
            Number of chunks deleted.
        """
        pass

    @abstractmethod
    def list_documents(self) -> List[Dict[str, Any]]:
        """Return a list of all indexed documents with metadata."""
        pass

    @abstractmethod
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieve all stored chunks and metadata for a specific document ID."""
        pass


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation of local, persistent vector storage."""

    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "docchat_docs"):
        """Initialize local ChromaDB persistent client.

        Args:
            persist_directory: Local filesystem path where ChromaDB stores indexes.
            collection_name: Name of the vector collection.
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        """Lazy-initialize ChromaDB client and collection on first access."""
        if self._collection is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self.persist_directory)
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(
                    f"ChromaDB collection '{self.collection_name}' ready at '{self.persist_directory}' "
                    f"({self._collection.count()} vectors)."
                )
            except ImportError:
                raise RuntimeError("chromadb package is not installed. Run: pip install chromadb")
        return self._collection

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """Store chunk dictionaries and their embeddings into ChromaDB.

        Args:
            chunks: List of chunk dictionaries containing 'chunk_id', 'text', and 'metadata'.
            embeddings: Optional precomputed list of embedding vectors. If None,
                        extracts 'embedding' from each chunk dict if available.
        """
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        ids = [c["chunk_id"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        if embeddings is None:
            embeddings = [c["embedding"] for c in chunks if "embedding" in c]

        self.add_documents(texts=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)

    def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        """Persist chunks and embeddings into ChromaDB.

        Existing chunks with the same IDs are overwritten (upsert semantics).
        """
        if not texts:
            return

        collection = self._get_collection()
        # ChromaDB upsert: add or update existing records
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(texts)} chunks into ChromaDB collection '{self.collection_name}'.")

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB collection for nearest neighbors (no doc_id filter)."""
        return self.search(query_embedding=query_embedding, top_k=top_k)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search with optional doc_id filter, returning structured chunk results.

        Args:
            query_embedding: The query vector.
            top_k: Max results to retrieve.
            doc_ids: If provided, only chunks from these doc_ids are searched.

        Returns:
            List of dicts with: text, filename, page, score (cosine similarity), chunk_id, doc_id.
        """
        collection = self._get_collection()
        total_vectors = collection.count()
        if total_vectors == 0:
            logger.warning("ChromaDB collection is empty — no documents indexed yet.")
            return []

        effective_top_k = min(top_k, total_vectors)

        # Build optional where clause for doc_id filtering
        where_clause = None
        if doc_ids:
            if len(doc_ids) == 1:
                where_clause = {"doc_id": {"$eq": doc_ids[0]}}
            else:
                where_clause = {"doc_id": {"$in": doc_ids}}

        try:
            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": effective_top_k,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_clause:
                query_kwargs["where"] = where_clause

            results = collection.query(**query_kwargs)
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            raise

        chunks: List[Dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        for doc_text, meta, distance, chunk_id in zip(documents, metadatas, distances, ids):
            # ChromaDB cosine space returns distance (0=identical, 2=opposite).
            # Convert to similarity score in [0, 1]: similarity = 1 - (distance / 2)
            similarity = round(1.0 - (distance / 2.0), 4)
            chunks.append({
                "chunk_id": chunk_id,
                "text": doc_text,
                "filename": meta.get("filename", "unknown"),
                "page": meta.get("page_number", None),
                "doc_id": meta.get("doc_id", ""),
                "score": similarity,
            })

        logger.debug(f"ChromaDB search returned {len(chunks)} chunks (top_k={effective_top_k}).")
        return chunks

    def delete_collection(self) -> None:
        """Delete the entire ChromaDB collection and reset state."""
        if self._client is not None:
            try:
                self._client.delete_collection(self.collection_name)
                logger.info(f"Deleted ChromaDB collection '{self.collection_name}'.")
            except Exception as e:
                logger.warning(f"Could not delete collection: {e}")
        self._collection = None

    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a given doc_id from the collection.

        Returns:
            Number of chunks deleted.
        """
        collection = self._get_collection()
        # Fetch IDs of all chunks belonging to this doc
        try:
            existing = collection.get(where={"doc_id": {"$eq": doc_id}}, include=[])
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} chunks for doc_id='{doc_id}'.")
            return len(ids_to_delete)
        except Exception as e:
            logger.error(f"Failed to delete chunks for doc_id='{doc_id}': {e}")
            return 0

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return metadata for all indexed documents, deduplicated by doc_id.

        Returns:
            List of dicts: {doc_id, filename, chunks_count, file_type}.
        """
        collection = self._get_collection()
        try:
            results = collection.get(include=["metadatas"])
        except Exception as e:
            logger.error(f"Failed to list documents from ChromaDB: {e}")
            return []

        metadatas = results.get("metadatas", [])
        docs_map: Dict[str, Dict[str, Any]] = {}

        for meta in metadatas:
            if not meta:
                continue
            doc_id = meta.get("doc_id", "")
            if not doc_id:
                continue
            if doc_id not in docs_map:
                docs_map[doc_id] = {
                    "doc_id": doc_id,
                    "filename": meta.get("filename", "unknown"),
                    "chunks_count": 0,
                    "file_type": meta.get("filename", "").split(".")[-1] if "." in meta.get("filename", "") else None,
                }
            docs_map[doc_id]["chunks_count"] += 1

        return list(docs_map.values())

    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieve all stored chunks and metadata for a specific document ID.

        Returns:
            List of dicts: {"chunk_id", "text", "metadata"} sorted by chunk_index.
        """
        collection = self._get_collection()
        try:
            results = collection.get(
                where={"doc_id": {"$eq": doc_id}},
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            ids = results.get("ids", [])
            chunks = []
            for chunk_id, text, meta in zip(ids, docs, metas):
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": meta,
                })
            chunks.sort(key=lambda c: (c.get("metadata") or {}).get("chunk_index", 0))
            return chunks
        except Exception as e:
            logger.error(f"Failed to fetch chunks for doc_id='{doc_id}': {e}")
            return []
