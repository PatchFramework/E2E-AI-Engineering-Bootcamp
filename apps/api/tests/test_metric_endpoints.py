import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app import app
from api.core.database import get_db
from api.models.db_models import (
    Base, Company, Document, FinancialFact, FinancialFactVersion,
    SourceLocation, DerivedMetricDefinition, DerivedMetricValue, DerivedMetricInputFact
)
from api.services.metric_calculation import MetricCalculationService

# Test SQLite in-memory setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_sample_company_facts(db: TestingSessionLocal) -> Company:
    # 1. Company
    company = Company(name="Acme Corp", ticker="ACME")
    db.add(company)
    db.flush()

    # 2. Document & Source Location
    doc = Document(
        company_id=company.id,
        filename="Acme_2025_Annual_Report.pdf",
        s3_path="filings/1/2025_FY/doc_123.pdf",
        content_hash="hash_123",
        fiscal_year=2025,
        fiscal_period="FY",
        document_type="Annual Report"
    )
    db.add(doc)
    db.flush()

    src_loc = SourceLocation(
        document_id=doc.id,
        page_number=42,
        displayed_page_number="42",
        section="Financial Highlights",
        text_snippet="EBITDA was EUR 178M for FY2025."
    )
    db.add(src_loc)
    db.flush()

    # 3. Facts for FY2025
    facts_data_2025 = [
        ("Revenue", 2400000000.0, "EUR"),
        ("EBITDA", 178000000.0, "EUR"),
        ("Total Debt", 1200000000.0, "EUR"),
        ("Cash", 360000000.0, "EUR"),
        ("Interest Expense", 63500000.0, "EUR"),
        ("Current Assets", 800000000.0, "EUR"),
        ("Current Liabilities", 550000000.0, "EUR"),
        ("Operating Cash Flow", 150000000.0, "EUR"),
        ("Capital Expenditures", 172000000.0, "EUR"),
        ("Total Assets", 3500000000.0, "EUR"),
        ("Total Equity", 1400000000.0, "EUR"),
    ]

    for concept, val, unit in facts_data_2025:
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=2025,
            fiscal_period="FY"
        )
        db.add(fact)
        db.flush()
        ver = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=val,
            unit=unit,
            origin="AI_GENERATED",
            verification_status="UNVERIFIED",
            source_location_id=src_loc.id if concept == "EBITDA" else None,
            is_current=True
        )
        db.add(ver)

    # 4. Facts for FY2024 (Prior year for YoY)
    facts_data_2024 = [
        ("Revenue", 2140000000.0, "EUR"),
        ("EBITDA", 185000000.0, "EUR"),
        ("Total Debt", 890000000.0, "EUR"),
        ("Cash", 335000000.0, "EUR"),
        ("Interest Expense", 46000000.0, "EUR"),
        ("Current Assets", 750000000.0, "EUR"),
        ("Current Liabilities", 500000000.0, "EUR"),
        ("Operating Cash Flow", 180000000.0, "EUR"),
        ("Capital Expenditures", 150000000.0, "EUR"),
        ("Total Assets", 3100000000.0, "EUR"),
        ("Total Equity", 1350000000.0, "EUR"),
    ]

    for concept, val, unit in facts_data_2024:
        fact = FinancialFact(
            company_id=company.id,
            concept=concept,
            fiscal_year=2024,
            fiscal_period="FY"
        )
        db.add(fact)
        db.flush()
        ver = FinancialFactVersion(
            fact_id=fact.id,
            version=1,
            value=val,
            unit=unit,
            origin="AI_GENERATED",
            verification_status="VERIFIED",
            is_current=True
        )
        db.add(ver)

    db.commit()
    return company


def test_get_company_metrics_endpoint(client, test_db):
    company = seed_sample_company_facts(test_db)
    
    response = client.get(f"/api/companies/{company.id}/metrics?fiscal_year=2025&fiscal_period=FY")
    assert response.status_code == 200
    metrics = response.json()
    assert len(metrics) > 0
    
    # Check Net Debt / EBITDA
    net_debt_ebitda = next((m for m in metrics if m["metric_name"] == "net_debt_to_ebitda"), None)
    assert net_debt_ebitda is not None
    assert net_debt_ebitda["category"] == "Leverage"
    # Net debt = 1.2B - 360M = 840M. 840M / 178M = 4.719...
    assert pytest.approx(net_debt_ebitda["current_value"], 0.01) == 4.72
    assert net_debt_ebitda["prior_value"] is not None
    assert net_debt_ebitda["yoy_change"] is not None
    assert len(net_debt_ebitda["history"]) >= 2


def test_get_metric_lineage_endpoint(client, test_db):
    company = seed_sample_company_facts(test_db)
    # Trigger metric calculation
    MetricCalculationService.recalculate_metrics_for_period(test_db, company.id, 2025, "FY")
    
    # Find derived metric
    derived_val = test_db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company.id,
        DerivedMetricValue.metric_name == "net_debt_to_ebitda",
        DerivedMetricValue.fiscal_year == 2025
    ).first()
    assert derived_val is not None
    
    response = client.get(f"/api/metrics/{derived_val.id}/lineage")
    assert response.status_code == 200
    lineage = response.json()
    assert lineage["metric_name"] == "net_debt_to_ebitda"
    assert len(lineage["input_facts"]) > 0
    
    # Check source location on EBITDA input
    ebitda_input = next((inf for inf in lineage["input_facts"] if inf["concept"] == "EBITDA"), None)
    assert ebitda_input is not None
    assert ebitda_input["source_location"]["page_number"] == 42
    assert ebitda_input["document"]["filename"] == "Acme_2025_Annual_Report.pdf"


def test_verify_and_correct_fact_endpoints(client, test_db):
    company = seed_sample_company_facts(test_db)
    ebitda_fact = test_db.query(FinancialFact).filter(
        FinancialFact.company_id == company.id,
        FinancialFact.concept == "EBITDA",
        FinancialFact.fiscal_year == 2025
    ).first()
    assert ebitda_fact is not None

    # 1. Verify fact
    res_verify = client.post(f"/api/facts/{ebitda_fact.id}/verify")
    assert res_verify.status_code == 200
    assert res_verify.json()["verification_status"] == "VERIFIED"

    # 2. Correct fact
    res_correct = client.post(
        f"/api/facts/{ebitda_fact.id}/correct",
        json={"value": 184000000.0, "change_reason": "Management adjusted EBITDA figure"}
    )
    assert res_correct.status_code == 200
    correct_data = res_correct.json()
    assert correct_data["fact"]["value"] == 184000000.0
    assert correct_data["fact"]["verification_status"] == "VERIFIED"
    assert "EBITDA Margin" in correct_data["affected_metrics"]
    assert "Net Debt / EBITDA" in correct_data["affected_metrics"]
    assert "Suggested Rating" in correct_data["affected_metrics"]

    # 3. Check that derived metrics were synchronously recalculated
    metrics_res = client.get(f"/api/companies/{company.id}/metrics?fiscal_year=2025")
    assert metrics_res.status_code == 200
    net_debt_ebitda = next((m for m in metrics_res.json() if m["metric_name"] == "net_debt_to_ebitda"), None)
    # Net debt = 840M / 184M = 4.5652...
    assert pytest.approx(net_debt_ebitda["current_value"], 0.01) == 4.57
    assert net_debt_ebitda["verification_status"] == "CORRECTED"
