import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from api.core.database import engine
from api.models.db_models import (
    Company, Document, SourceLocation, FinancialFact, FinancialFactVersion
)

@pytest.fixture(scope="function")
def db_session():
    # Start a transaction and rollback at the end of each test
    connection = engine.connect()
    transaction = connection.begin()
    
    # Use join_transaction_mode="create_savepoint" so that session.commit()
    # operates on a savepoint (nested transaction) and rollback() rolls back to savepoint.
    # This prevents the outer transaction from committing or being deassociated.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

def test_company_creation(db_session: Session):
    # Test creating a company
    company = Company(
        name="Test ACME Corp",
        ticker="TACME",
        industry="Technology",
        description="Fictional testing company"
    )
    db_session.add(company)
    db_session.commit()
    
    assert company.id is not None
    assert company.name == "Test ACME Corp"
    assert company.ticker == "TACME"

def test_document_and_source_location(db_session: Session):
    company = Company(name="Doc Test Corp", ticker="DTC")
    db_session.add(company)
    db_session.commit()
    
    document = Document(
        company_id=company.id,
        filename="filing.pdf",
        s3_path="s3://filings/dtc/2026/filing.pdf",
        content_hash="unique_sha256_hash_123",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    db_session.add(document)
    db_session.commit()
    
    assert document.id is not None
    assert document.content_hash == "unique_sha256_hash_123"
    
    source = SourceLocation(
        document_id=document.id,
        page_number=12,
        section="Financial Condition",
        text_snippet="EBITDA was 10.5 million",
        bounding_box={"x_min": 10.0, "y_min": 20.0, "x_max": 50.0, "y_max": 60.0},
        object_storage_path="s3://filings/dtc/2026/page_12.png",
        content_hash="source_snippet_hash_456"
    )
    db_session.add(source)
    db_session.commit()
    
    assert source.id is not None
    assert source.bounding_box["x_min"] == 10.0

def test_financial_fact_version_workflow(db_session: Session):
    company = Company(name="Fact Test Corp", ticker="FTC")
    db_session.add(company)
    db_session.commit()
    
    fact = FinancialFact(
        company_id=company.id,
        concept="EBITDA",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    db_session.add(fact)
    db_session.commit()
    
    # 1. Add version 1 (AI_GENERATED, UNVERIFIED, current)
    v1 = FinancialFactVersion(
        fact_id=fact.id,
        version=1,
        value=10500000.0,
        unit="EUR",
        origin="AI_GENERATED",
        verification_status="UNVERIFIED",
        is_current=True
    )
    db_session.add(v1)
    db_session.commit()
    
    assert v1.id is not None
    assert v1.is_current is True

    # 2. Try adding a second version with is_current=True (should fail unique index)
    v2_fail = FinancialFactVersion(
        fact_id=fact.id,
        version=2,
        value=11000000.0,
        unit="EUR",
        origin="ANALYST_CORRECTED",
        verification_status="VERIFIED",
        is_current=True  # Both v1 and v2 cannot be current
    )
    db_session.add(v2_fail)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 3. Add version 2 with is_current=True after marking version 1 as not current
    v1.is_current = False
    db_session.commit()
    
    v2_ok = FinancialFactVersion(
        fact_id=fact.id,
        version=2,
        value=11000000.0,
        unit="EUR",
        origin="ANALYST_CORRECTED",
        verification_status="VERIFIED",
        is_current=True
    )
    db_session.add(v2_ok)
    db_session.commit()
    
    assert v2_ok.id is not None
    assert v2_ok.is_current is True

def test_check_constraints(db_session: Session):
    company = Company(name="Constraint Test Corp", ticker="CTC")
    db_session.add(company)
    db_session.commit()
    
    fact = FinancialFact(
        company_id=company.id,
        concept="Revenue",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    db_session.add(fact)
    db_session.commit()
    
    # Try invalid verification_status
    v_invalid = FinancialFactVersion(
        fact_id=fact.id,
        version=1,
        value=50000000.0,
        unit="EUR",
        origin="AI_GENERATED",
        verification_status="APPROVED",  # Invalid (must be UNVERIFIED or VERIFIED)
        is_current=True
    )
    db_session.add(v_invalid)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    
    assert "chk_fact_version_verification_status" in str(exc_info.value)

    # Try invalid origin
    v_invalid_origin = FinancialFactVersion(
        fact_id=fact.id,
        version=1,
        value=50000000.0,
        unit="EUR",
        origin="USER_ENTERED",  # Invalid (must be AI_GENERATED, ANALYST_CORRECTED, ANALYST_ENTERED)
        verification_status="UNVERIFIED",
        is_current=True
    )
    db_session.add(v_invalid_origin)
    with pytest.raises(IntegrityError) as exc_info_origin:
        db_session.commit()
    db_session.rollback()
    
    assert "chk_fact_version_origin" in str(exc_info_origin.value)
