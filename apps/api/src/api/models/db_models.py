from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    documents = relationship("Document", back_populates="company")
    facts = relationship("FinancialFact", back_populates="company")


class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    filename = Column(String, nullable=False)
    s3_path = Column(String, nullable=False)
    content_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="documents")
    source_locations = relationship("SourceLocation", back_populates="document")


class SourceLocation(Base):
    __tablename__ = 'source_locations'
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    page_number = Column(Integer, nullable=False)
    section = Column(String)
    text_snippet = Column(Text)
    bounding_box = Column(String)  # Stored as json string
    
    document = relationship("Document", back_populates="source_locations")


class FinancialFact(Base):
    __tablename__ = 'financial_facts'
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    concept = Column(String, index=True, nullable=False)  # e.g., EBITDA
    fiscal_year = Column(Integer, nullable=False)
    fiscal_period = Column(String, nullable=False)  # FY, Q1, etc.
    
    company = relationship("Company", back_populates="facts")
    versions = relationship("FinancialFactVersion", back_populates="fact")


class FinancialFactVersion(Base):
    __tablename__ = 'financial_fact_versions'
    
    id = Column(Integer, primary_key=True, index=True)
    fact_id = Column(Integer, ForeignKey('financial_facts.id'), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, default="EUR")
    origin = Column(String, default="AI_GENERATED")  # AI_GENERATED, ANALYST_CORRECTED
    verification_status = Column(String, default="UNVERIFIED")  # UNVERIFIED, VERIFIED
    source_location_id = Column(Integer, ForeignKey('source_locations.id'), nullable=True)
    change_reason = Column(String)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)

    fact = relationship("FinancialFact", back_populates="versions")


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
