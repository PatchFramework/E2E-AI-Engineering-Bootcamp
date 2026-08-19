import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from sqlalchemy.orm import Session
from api.core.database import engine
from api.models.db_models import (
    Company, Document, SourceLocation, FinancialFact, FinancialFactVersion,
    DerivedMetricValue, DataQualityIssue
)
from api.services.metric_calculation import MetricCalculationService
from pipelines.tasks.validation import validate_facts

from sqlalchemy import create_engine, event
from api.models.db_models import Base

@pytest.fixture(scope="function")
def db_session():
    mem_engine = create_engine("sqlite:///:memory:")

    @event.listens_for(mem_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=mem_engine)
    session = Session(bind=mem_engine)
    yield session
    session.close()

def test_derived_metric_recalculation(db_session: Session):
    # Setup company
    company = Company(name="Metric Calc Corp", ticker="MCC")
    db_session.add(company)
    db_session.commit()

    # Setup facts (Total Debt, Cash, EBITDA, Revenue, Interest Expense)
    year = 2026
    period = "FY"

    def add_fact(concept: str, value: float):
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=year,
            fiscal_period=period
        )
        db_session.add(fact)
        db_session.flush()

        version = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=value,
            unit="EUR",
            is_current=True
        )
        db_session.add(version)
        db_session.flush()

    # Add the base facts
    add_fact("Revenue", 1000000.0)
    add_fact("EBITDA", 250000.0)
    add_fact("Total Debt", 500000.0)
    add_fact("Cash", 100000.0)
    add_fact("Interest Expense", 50000.0)
    db_session.commit()

    # Recalculate
    MetricCalculationService.recalculate_metrics_for_period(
        db_session,
        company_id=company.id,
        year=year,
        period=period
    )

    # Verify calculated values in database
    metrics = db_session.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.fiscal_year == year,
        DerivedMetricValue.fiscal_period == period
    ).all()

    metrics_map = {m.metric_name: m.value for m in metrics}

    # Expected:
    # Net Debt = Total Debt (500k) - Cash (100k) = 400k
    # Net Debt / EBITDA = 400k / 250k = 1.6
    # EBITDA Margin = 250k / 1M = 0.25 (25%)
    # Interest Coverage = 250k / 50k = 5.0
    assert metrics_map["net_debt"] == 400000.0
    assert metrics_map["net_debt_to_ebitda"] == 1.6
    assert metrics_map["ebitda_margin"] == 0.25
    assert metrics_map["interest_coverage"] == 5.0


def test_accounting_math_validation_warnings(db_session: Session):
    # Setup company and document
    company = Company(name="Validation Warn Corp", ticker="VWC")
    db_session.add(company)
    db_session.commit()

    doc = Document(
        company_id=company.id,
        filename="test.pdf",
        s3_path="filings/test.pdf",
        content_hash="some_content_hash_abc",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    db_session.add(doc)
    db_session.commit()

    # We add inconsistent facts:
    # Total Assets = 1,000,000
    # Total Liabilities = 600,000
    # Total Equity = 300,000
    # (Discrepancy: 1,000,000 != 600,000 + 300,000)
    def add_fact(concept: str, value: float):
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=2026,
            fiscal_period="FY"
        )
        db_session.add(fact)
        db_session.flush()

        version = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=value,
            unit="EUR",
            is_current=True
        )
        db_session.add(version)
        db_session.flush()

    add_fact("Total Assets", 1000000.0)
    add_fact("Total Liabilities", 600000.0)
    add_fact("Total Equity", 300000.0)
    db_session.commit()

    # Run validation task
    validate_facts({
        "document_id": doc.id,
        "company_id": company.id,
        "fiscal_year": 2026,
        "fiscal_period": "FY",
        "fact_ids": []
    }, db_session=db_session)

    # Verify DataQualityIssue was created
    issues = db_session.query(DataQualityIssue).filter(
        DataQualityIssue.company_id == company.id,
        DataQualityIssue.document_id == doc.id
    ).all()

    assert len(issues) == 1
    assert issues[0].issue_type == "ACCOUNTING_RULE_VIOLATION"
    assert "Total Assets" in issues[0].concept
    assert "1000000" in issues[0].message


def test_prior_year_reconciliation_warning(db_session: Session):
    # Setup company and document
    company = Company(name="Recon Test Corp", ticker="RTC")
    db_session.add(company)
    db_session.commit()

    doc = Document(
        company_id=company.id,
        filename="filing_2026.pdf",
        s3_path="filings/filing_2026.pdf",
        content_hash="recon_content_hash_123",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    db_session.add(doc)
    db_session.commit()

    # 1. Setup an existing APPROVED fact in DB for prior year (2025):
    # Revenue for 2025 = 800,000
    doc_2025 = Document(
        company_id=company.id,
        filename="filing_2025.pdf",
        s3_path="filings/filing_2025.pdf",
        content_hash="recon_content_hash_999",
        fiscal_year=2025,
        fiscal_period="FY"
    )
    db_session.add(doc_2025)
    db_session.flush()

    source_loc_2025 = SourceLocation(
        document_id=doc_2025.id,
        page_number=4,
        content_hash="old_2025_revenue_loc"
    )
    db_session.add(source_loc_2025)
    db_session.flush()

    fact_2025 = FinancialFact(
        company_id=company.id,
        concept="Revenue",
        fiscal_year=2025,
        fiscal_period="FY"
    )
    db_session.add(fact_2025)
    db_session.flush()

    version_2025 = FinancialFactVersion(
        fact_id=fact_2025.id,
        version=1,
        value=800000.0,
        unit="EUR",
        is_current=True,
        source_location_id=source_loc_2025.id
    )
    db_session.add(version_2025)
    db_session.commit()

    # 2. Extract facts during 2026 filing processing.
    # The 2026 document reports 2025 Revenue differently:
    # E.g. extracted 2025 Revenue = 850,000 (which is different from 800,000 in DB)
    fact_new_2025 = FinancialFact(
        company_id=company.id,
        concept="Revenue",
        fiscal_year=2025,
        fiscal_period="FY"
    )
    # Note: Since the company_id, concept, year, period are the same, the extraction logic
    # would fetch the same FinancialFact record (fact_2025.id).
    # Let's add a new current version with value 850,000, simulating extraction from the new document:
    version_2025.is_current = False
    
    source_loc_new = SourceLocation(
        document_id=doc.id,
        page_number=3,
        content_hash="new_2025_revenue_loc"
    )
    db_session.add(source_loc_new)
    db_session.flush()

    new_version_2025 = FinancialFactVersion(
        fact_id=fact_2025.id,
        version=2,
        value=850000.0,
        unit="EUR",
        is_current=True,
        source_location_id=source_loc_new.id
    )
    db_session.add(new_version_2025)
    db_session.commit()

    # Run validation task
    validate_facts({
        "document_id": doc.id,
        "company_id": company.id,
        "fiscal_year": 2026,
        "fiscal_period": "FY",
        "fact_ids": []
    }, db_session=db_session)

    # Verify DataQualityIssue was created for the reconciliation mismatch
    issues = db_session.query(DataQualityIssue).filter(
        DataQualityIssue.company_id == company.id,
        DataQualityIssue.issue_type == "RECONCILIATION_DISCREPANCY"
    ).all()

    assert len(issues) == 1
    assert "Revenue" in issues[0].concept
    assert "850000" in issues[0].message
    assert "800000" in issues[0].message
