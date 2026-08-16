from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text, Index, CheckConstraint, text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String, index=True)
    industry = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    documents = relationship("Document", back_populates="company", cascade="all, delete-orphan")
    facts = relationship("FinancialFact", back_populates="company", cascade="all, delete-orphan")
    document_chunks = relationship("DocumentChunk", back_populates="company", cascade="all, delete-orphan")
    quality_issues = relationship("DataQualityIssue", back_populates="company", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    filename = Column(String, nullable=False)
    s3_path = Column(String, nullable=False)
    content_hash = Column(String, unique=True, nullable=False)
    fiscal_year = Column(Integer, index=True)
    fiscal_period = Column(String, index=True)  # FY, Q1, etc.
    document_type = Column(String, index=True)  # 10-K, 10-Q, Annual Report
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="documents")
    source_locations = relationship("SourceLocation", back_populates="document", cascade="all, delete-orphan")
    document_chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    quality_issues = relationship("DataQualityIssue", back_populates="document", cascade="all, delete-orphan")


class SourceLocation(Base):
    __tablename__ = 'source_locations'
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    page_number = Column(Integer, nullable=False)
    displayed_page_number = Column(String)  # printed label (e.g. Roman numerals)
    section = Column(String)
    section_path = Column(String)  # hierarchical path
    text_snippet = Column(Text)
    bounding_box = Column(JSONB)  # Stored as JSON coordinate info
    object_storage_path = Column(String)  # Reference to cropped page/image in MinIO
    content_hash = Column(String)  # Unique hash of the location content
    
    document = relationship("Document", back_populates="source_locations")


class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    page_number = Column(Integer, nullable=False)
    displayed_page_number = Column(String)
    section_path = Column(String)
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # 1536 dims for openai
    chunk_metadata = Column(JSONB)  # fiscal_year, concepts_contained, affected_metrics
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="document_chunks")
    document = relationship("Document", back_populates="document_chunks")


class DataQualityIssue(Base):
    __tablename__ = 'data_quality_issues'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    issue_type = Column(String, nullable=False)  # ACCOUNTING_RULE_VIOLATION, RECONCILIATION_DISCREPANCY, SANITY_CHECK_WARNING
    severity = Column(String, nullable=False)  # WARNING, ERROR
    concept = Column(String)
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="quality_issues")
    document = relationship("Document", back_populates="quality_issues")



class FinancialFact(Base):
    __tablename__ = 'financial_facts'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    concept = Column(String, index=True, nullable=False)  # e.g., EBITDA
    fiscal_year = Column(Integer, nullable=False)
    fiscal_period = Column(String, nullable=False)  # FY, Q1, etc.
    fiscal_period_start = Column(DateTime)
    fiscal_period_end = Column(DateTime)
    
    company = relationship("Company", back_populates="facts")
    versions = relationship("FinancialFactVersion", back_populates="fact", cascade="all, delete-orphan")


class FinancialFactVersion(Base):
    __tablename__ = 'financial_fact_versions'
    
    id = Column(Integer, primary_key=True, index=True)
    fact_id = Column(Integer, ForeignKey('financial_facts.id'), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    value = Column(Float, nullable=False)
    unit = Column(String, default="EUR")
    origin = Column(
        String,
        CheckConstraint("origin IN ('AI_GENERATED', 'ANALYST_CORRECTED', 'ANALYST_ENTERED')"),
        default="AI_GENERATED",
        nullable=False
    )
    verification_status = Column(
        String,
        CheckConstraint("verification_status IN ('UNVERIFIED', 'VERIFIED')"),
        default="UNVERIFIED",
        nullable=False
    )
    source_location_id = Column(Integer, ForeignKey('source_locations.id'), nullable=True)
    change_reason = Column(String)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)

    fact = relationship("FinancialFact", back_populates="versions")

    __table_args__ = (
        Index(
            'ix_fact_versions_current_uniq',
            'fact_id',
            postgresql_where=text('is_current = true'),
            unique=True
        ),
    )


class DerivedMetricValue(Base):
    __tablename__ = 'derived_metric_values'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    metric_name = Column(String, index=True, nullable=False)  # e.g., net_debt_to_ebitda
    value = Column(Float)
    fiscal_year = Column(Integer, nullable=False)
    fiscal_period = Column(String, nullable=False)
    calculated_at = Column(DateTime, default=datetime.utcnow)
    calculation_version = Column(String)
    input_fact_versions = Column(String)  # JSON representation of fact versions used


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)  # FACT_CORRECTED, etc.
    entity_type = Column(String)
    entity_id = Column(Integer)
    company_id = Column(Integer)
    previous_value = Column(String)
    new_value = Column(String)
    reason = Column(Text)
    correlation_id = Column(String, index=True)
