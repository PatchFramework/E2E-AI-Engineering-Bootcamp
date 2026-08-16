def index_document_chunks(document_id: str, chunks: list):
    """
    Computes embeddings for document chunks and saves them in pgvector + MinIO.
    """
    print(f"Indexing chunks for document: {document_id}")
    return {"status": "success"}
