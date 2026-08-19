"""
test_metrics_calculation_service.py — Integration and relational lineage tests for MetricCalculationService.

Tests:
  1. Synchronous recalculation of all 6 KPI categories.
  2. Multi-period YoY metric calculation (Revenue Growth with prior-period dependency).
  3. Proper handling of missing facts (marking status=UNAVAILABLE with status_reason).
  4. Relational lineage integrity and zero data duplication:
     Traversing DerivedMetricValue -> DerivedMetricInputFact -> FinancialFactVersion -> SourceLocation -> Document -> DocumentChunk.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from api.models.db_models import (
    Base, Company, Document, SourceLocation, DocumentChunk,
    FinancialFact, FinancialFactVersion, DerivedMetricDefinition,
    DerivedMetricValue, DerivedMetricInputFact
)
from api.services.metric_calculation import MetricCalculationService


@pytest.fixture(scope="function")
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")

    # Enable SQLite foreign key constraints
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.close()


def test_recalculate_all_categories_standard_facts(in_memory_db: Session):
    # 1. Create company and document
    company = Company(name="Acme Corp", ticker="ACM")
    in_memory_db.add(company)
    in_memory_db.flush()

    doc = Document(
        company_id=company.id,
        filename="acme_fy2026.pdf",
        s3_path="filings/1/2026_FY/annual_report.pdf",
        content_hash="hash_acme_2026",
        fiscal_year=2026,
        fiscal_period="FY",
        document_type="10-K"
    )
    in_memory_db.add(doc)
    in_memory_db.flush()

    loc = SourceLocation(
        document_id=doc.id,
        page_number=12,
        displayed_page_number="10",
        section="Financial Highlights",
        section_path="Item 8 > Financial Highlights",
        text_snippet="Total Revenue was $1,000,000. EBITDA reached $250,000.",
        content_hash="loc_hash_12"
    )
    in_memory_db.add(loc)
    in_memory_db.flush()

    def add_fact(concept: str, value: float, year: int = 2026, period: str = "FY") -> FinancialFactVersion:
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=year,
            fiscal_period=period
        )
        in_memory_db.add(fact)
        in_memory_db.flush()

        version = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=value,
            unit="EUR",
            origin="AI_GENERATED",
            verification_status="UNVERIFIED",
            source_location_id=loc.id,
            is_current=True
        )
        in_memory_db.add(version)
        in_memory_db.flush()
        return version

    # Profitability & Core Facts
    add_fact("Revenue", 1000000.0)
    add_fact("Cost of Goods Sold", 600000.0)
    add_fact("Gross Profit", 400000.0)
    add_fact("Operating Expense", 150000.0)
    add_fact("Operating Income", 250000.0)
    add_fact("EBITDA", 250000.0)
    add_fact("Net Income", 180000.0)

    # Leverage Facts
    add_fact("Total Debt", 500000.0)
    add_fact("Cash", 100000.0)
    add_fact("Total Equity", 500000.0)
    add_fact("Short-term Debt", 50000.0)

    # Coverage Facts
    add_fact("Interest Expense", 50000.0)

    # Liquidity Facts
    add_fact("Current Assets", 600000.0)
    add_fact("Current Liabilities", 300000.0)
    add_fact("Receivables", 150000.0)
    add_fact("Short-term Investments", 50000.0)

    # Cash Flow Facts
    add_fact("Operating Cash Flow", 300000.0)
    add_fact("Capital Expenditures", 100000.0)

    # Balance Sheet Facts
    add_fact("Total Assets", 1200000.0)
    add_fact("Total Liabilities", 700000.0)

    in_memory_db.commit()

    # 2. Recalculate metrics for period
    summary = MetricCalculationService.recalculate_metrics_for_period(
        in_memory_db,
        company_id=company.id,
        year=2026,
        period="FY"
    )

    assert summary["status"] == "success"
    assert summary["metrics_available"] > 0

    # 3. Verify specific calculated metric values in database
    metrics = in_memory_db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.fiscal_year == 2026,
        DerivedMetricValue.fiscal_period == "FY"
    ).all()

    metric_map = {m.metric_name: m for m in metrics}

    # Net Debt = 500k - 100k = 400k
    assert metric_map["net_debt"].value == 400000.0
    assert metric_map["net_debt"].status == "AVAILABLE"

    # Net Debt / EBITDA = 400k / 250k = 1.6x
    assert metric_map["net_debt_to_ebitda"].value == pytest.approx(1.6)

    # Gross Margin = 400k / 1M = 0.4 (40%)
    assert metric_map["gross_margin"].value == pytest.approx(0.4)

    # EBITDA Margin = 250k / 1M = 0.25 (25%)
    assert metric_map["ebitda_margin"].value == pytest.approx(0.25)

    # EBITDA / Interest = 250k / 50k = 5.0x
    assert metric_map["ebitda_to_interest"].value == pytest.approx(5.0)

    # Current Ratio = 600k / 300k = 2.0
    assert metric_map["current_ratio"].value == pytest.approx(2.0)

    # Quick Ratio = (100k + 50k + 150k) / 300k = 1.0
    assert metric_map["quick_ratio"].value == pytest.approx(1.0)

    # Free Cash Flow = 300k - 100k = 200k
    assert metric_map["free_cash_flow"].value == 200000.0

    # FCF / Debt = 200k / 500k = 0.4 (40%)
    assert metric_map["fcf_to_debt"].value == pytest.approx(0.4)

    # 4. Verify Relational Lineage records
    net_debt_metric = metric_map["net_debt"]
    input_links = in_memory_db.query(DerivedMetricInputFact).filter(
        DerivedMetricInputFact.derived_metric_id == net_debt_metric.id
    ).all()

    assert len(input_links) == 2
    concept_names = {link.concept_name for link in input_links}
    assert concept_names == {"Total Debt", "Cash"}


def test_multi_period_revenue_growth(in_memory_db: Session):
    company = Company(name="Growth Corp", ticker="GRW")
    in_memory_db.add(company)
    in_memory_db.flush()

    def add_revenue(value: float, year: int):
        fact = FinancialFact(
            company_id=company.id,
            concept="Revenue",
            fiscal_year=year,
            fiscal_period="FY"
        )
        in_memory_db.add(fact)
        in_memory_db.flush()

        version = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=value,
            unit="EUR",
            is_current=True
        )
        in_memory_db.add(version)
        in_memory_db.flush()

    # Prior year 2025: 1,000,000
    add_revenue(1000000.0, 2025)
    # Current year 2026: 1,250,000 (+25%)
    add_revenue(1250000.0, 2026)
    in_memory_db.commit()

    MetricCalculationService.recalculate_metrics_for_period(
        in_memory_db,
        company_id=company.id,
        year=2026,
        period="FY"
    )

    growth_metric = in_memory_db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.metric_name == "revenue_growth",
        DerivedMetricValue.fiscal_year == 2026
    ).first()

    assert growth_metric is not None
    assert growth_metric.status == "AVAILABLE"
    assert growth_metric.value == pytest.approx(0.25)

    # Check relational links for prior period
    links = in_memory_db.query(DerivedMetricInputFact).filter(
        DerivedMetricInputFact.derived_metric_id == growth_metric.id
    ).all()
    roles = {l.relationship_role for l in links}
    assert "PRIOR_PERIOD" in roles


def test_unavailable_status_when_facts_missing(in_memory_db: Session):
    company = Company(name="Empty Corp", ticker="EMP")
    in_memory_db.add(company)
    in_memory_db.commit()

    MetricCalculationService.recalculate_metrics_for_period(
        in_memory_db,
        company_id=company.id,
        year=2026,
        period="FY"
    )

    # All metrics should be UNAVAILABLE
    metrics = in_memory_db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.fiscal_year == 2026
    ).all()

    assert len(metrics) > 0
    for m in metrics:
        assert m.status == "UNAVAILABLE"
        assert m.status_reason is not None


def test_metric_lineage_retrieval_and_cited_chunks(in_memory_db: Session):
    company = Company(name="Lineage Corp", ticker="LIN")
    in_memory_db.add(company)
    in_memory_db.flush()

    doc = Document(
        company_id=company.id,
        filename="filing.pdf",
        s3_path="filings/lin/2026_FY/report.pdf",
        content_hash="lin_hash_99",
        fiscal_year=2026,
        fiscal_period="FY"
    )
    in_memory_db.add(doc)
    in_memory_db.flush()

    loc = SourceLocation(
        document_id=doc.id,
        page_number=5,
        displayed_page_number="3",
        section="Balance Sheet",
        section_path="Item 8 > Balance Sheet",
        text_snippet="Cash and cash equivalents were $100M. Total Debt was $300M.",
        bounding_box={"x0": 10, "y0": 20, "x1": 200, "y1": 50},
        content_hash="loc_hash_5"
    )
    in_memory_db.add(loc)
    in_memory_db.flush()

    chunk = DocumentChunk(
        company_id=company.id,
        document_id=doc.id,
        page_number=5,
        displayed_page_number="3",
        section_path="Item 8 > Balance Sheet",
        chunk_index=0,
        text_content="Section: Item 8 > Balance Sheet\nCash was $100M and Total Debt was $300M.",
        embedding=[0.0] * 1536,
        chunk_metadata={"concepts_contained": ["Cash", "Total Debt"]}
    )
    in_memory_db.add(chunk)
    in_memory_db.flush()

    def add_fact(concept: str, value: float):
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=2026,
            fiscal_period="FY"
        )
        in_memory_db.add(fact)
        in_memory_db.flush()

        version = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=value,
            unit="EUR",
            source_location_id=loc.id,
            is_current=True
        )
        in_memory_db.add(version)
        in_memory_db.flush()

    add_fact("Total Debt", 300000000.0)
    add_fact("Cash", 100000000.0)
    in_memory_db.commit()

    MetricCalculationService.recalculate_metrics_for_period(
        in_memory_db,
        company_id=company.id,
        year=2026,
        period="FY"
    )

    net_debt_metric = in_memory_db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.metric_name == "net_debt"
    ).first()

    # Query relational lineage
    lineage = MetricCalculationService.get_metric_lineage(in_memory_db, net_debt_metric.id)

    assert lineage is not None
    assert lineage["metric_name"] == "net_debt"
    assert lineage["display_name"] == "Net Debt"
    assert lineage["category"] == "Leverage"
    assert lineage["value"] == 200000000.0
    assert lineage["status"] == "AVAILABLE"

    # Verify input facts provenance
    assert len(lineage["input_facts"]) == 2
    for input_f in lineage["input_facts"]:
        assert input_f["source_location"]["page_number"] == 5
        assert input_f["source_location"]["displayed_page_number"] == "3"
        assert "Cash and cash equivalents" in input_f["source_location"]["text_snippet"]
        assert input_f["document"]["filename"] == "filing.pdf"

    # Verify cited chunks for RAG
    assert len(lineage["cited_chunks"]) == 1
    assert lineage["cited_chunks"][0]["page_number"] == 5
    assert "Balance Sheet" in lineage["cited_chunks"][0]["text_content"]
