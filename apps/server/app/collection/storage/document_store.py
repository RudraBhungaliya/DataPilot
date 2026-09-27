"""
Raw Document Store.
Persists and retrieves raw collected documents (HTML, JSON, XML, Text).
Maintains content integrity, content hashes, and provenance metadata.
"""

import hashlib
from typing import Optional, List, Dict
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.collection.schemas import RawDocument, DocumentReference
from app.models.document import Document
from app.core.logger import logger


class RawDocumentStore:
    """
    Storage layer for raw collected documents.
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        # In-memory document fallback store for tests or local execution
        self._memory_store: Dict[str, RawDocument] = {}

    @staticmethod
    def compute_hash(content: str) -> str:
        """Computes SHA-256 hash of document content."""
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

    async def save(
        self,
        document: RawDocument,
        db: Optional[AsyncSession] = None,
    ) -> DocumentReference:
        """
        Saves a raw document and returns a lightweight DocumentReference.
        """
        if not document.content_hash:
            document.content_hash = self.compute_hash(document.content)

        # Store in memory cache
        self._memory_store[document.document_id] = document

        target_db = db or self.session
        # Store in SQL Database if session is provided
        if target_db is not None:
            try:
                db_doc = Document(
                    id=document.document_id,
                    job_id=document.job_id,
                    source_id=document.source_id,
                    url=document.url,
                    canonical_url=document.canonical_url,
                    content_type=document.content_type,
                    content=document.content,
                    content_hash=document.content_hash,
                    status_code=document.status_code,
                    collected_at=document.collected_at or datetime.now(timezone.utc),
                    metadata_=document.metadata,
                )
                target_db.add(db_doc)
                await target_db.commit()
                await target_db.refresh(db_doc)
                logger.debug(f"Document {document.document_id} persisted to database.")
            except Exception as e:
                logger.warning(f"Could not persist document {document.document_id} to DB (saved in memory): {e}")
                await target_db.rollback()

        return DocumentReference(
            document_id=document.document_id,
            source_id=document.source_id,
            url=document.url,
            canonical_url=document.canonical_url,
            content_type=document.content_type,
            status_code=document.status_code,
            content_location=f"storage://documents/{document.document_id}",
            content_hash=document.content_hash,
            collected_at=document.collected_at.isoformat() if document.collected_at else datetime.now(timezone.utc).isoformat(),
            size_bytes=len(document.content.encode("utf-8")),
            collector=document.metadata.get("collector"),
            zyte_used=document.metadata.get("zyte_used", False),
            content=document.content,
        )

    async def get(
        self,
        document_id: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[RawDocument]:
        """
        Retrieves raw document by ID.
        """
        if db is not None:
            try:
                stmt = select(Document).where(Document.id == document_id)
                res = await db.execute(stmt)
                db_doc = res.scalar_one_or_none()
                if db_doc:
                    return RawDocument(
                        document_id=db_doc.id,
                        job_id=db_doc.job_id,
                        source_id=db_doc.source_id,
                        url=db_doc.url,
                        canonical_url=db_doc.canonical_url,
                        content_type=db_doc.content_type,
                        content=db_doc.content,
                        content_hash=db_doc.content_hash,
                        status_code=db_doc.status_code,
                        collected_at=db_doc.collected_at,
                        metadata=db_doc.metadata_,
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch document {document_id} from DB: {e}")

        return self._memory_store.get(document_id)

    async def list_by_job(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
        db: Optional[AsyncSession] = None,
    ) -> List[RawDocument]:
        """
        Lists documents collected for a specific collection job.
        """
        if db is not None:
            try:
                stmt = (
                    select(Document)
                    .where(Document.job_id == job_id)
                    .order_by(desc(Document.collected_at))
                    .offset(offset)
                    .limit(limit)
                )
                res = await db.execute(stmt)
                db_docs = res.scalars().all()
                if db_docs:
                    return [
                        RawDocument(
                            document_id=d.id,
                            job_id=d.job_id,
                            source_id=d.source_id,
                            url=d.url,
                            canonical_url=d.canonical_url,
                            content_type=d.content_type,
                            content=d.content,
                            content_hash=d.content_hash,
                            status_code=d.status_code,
                            collected_at=d.collected_at,
                            metadata=d.metadata_,
                        )
                        for d in db_docs
                    ]
            except Exception as e:
                logger.warning(f"Failed to query documents by job {job_id} from DB: {e}")

        # Fallback to memory
        matched = [doc for doc in self._memory_store.values() if doc.job_id == job_id]
        return matched[offset : offset + limit]

    async def list_by_source(
        self,
        source_id: str,
        limit: int = 100,
        db: Optional[AsyncSession] = None,
    ) -> List[RawDocument]:
        """
        Lists documents collected from a specific source.
        """
        if db is not None:
            try:
                stmt = (
                    select(Document)
                    .where(Document.source_id == source_id)
                    .order_by(desc(Document.collected_at))
                    .limit(limit)
                )
                res = await db.execute(stmt)
                db_docs = res.scalars().all()
                if db_docs:
                    return [
                        RawDocument(
                            document_id=d.id,
                            job_id=d.job_id,
                            source_id=d.source_id,
                            url=d.url,
                            canonical_url=d.canonical_url,
                            content_type=d.content_type,
                            content=d.content,
                            content_hash=d.content_hash,
                            status_code=d.status_code,
                            collected_at=d.collected_at,
                            metadata=d.metadata_,
                        )
                        for d in db_docs
                    ]
            except Exception as e:
                logger.warning(f"Failed to query documents by source {source_id} from DB: {e}")

        matched = [doc for doc in self._memory_store.values() if doc.source_id == source_id]
        return matched[:limit]
