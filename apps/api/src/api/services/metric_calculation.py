import logging
import json
from datetime import datetime
from api.models.db_models import FinancialFact, FinancialFactVersion, DerivedMetricValue

logger = logging.getLogger(__name__)

# Business KPI Formulas

def calculate_net_debt(total_debt: float, cash: float) -> float:
    return total_debt - cash

def calculate_net_debt_to_ebitda(net_debt: float, ebitda: float) -> float:
    if ebitda == 0:
        logger.warning("EBITDA is 0, cannot calculate Net Debt / EBITDA")
        return float('nan')
    return net_debt / ebitda

def calculate_ebitda_margin(ebitda: float, revenue: float) -> float:
    if revenue == 0:
        logger.warning("Revenue is 0, cannot calculate EBITDA Margin")
        return float('nan')
    return ebitda / revenue

def calculate_interest_coverage(ebitda: float, interest_expense: float) -> float:
    if interest_expense == 0:
        logger.warning("Interest expense is 0, cannot calculate EBITDA Interest Coverage")
        return float('nan')
    return ebitda / interest_expense


class MetricCalculationService:
    @staticmethod
    def recalculate_metrics_for_period(db_session, company_id: int, year: int, period: str):
        """
        Synchronously fetches current active facts for a given company, year, and period,
        recalculates all derived KPIs, and updates the snapshots table.
        """
        logger.info(f"Triggering synchronous metric recalculation for company {company_id} in {year} {period}")
        
        # 1. Fetch current active versions of all facts for the period
        results = db_session.query(FinancialFact, FinancialFactVersion).join(
            FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
        ).filter(
            FinancialFact.company_id == company_id,
            FinancialFact.fiscal_year == year,
            FinancialFact.fiscal_period == period,
            FinancialFactVersion.is_current == True
        ).all()

        # 2. Build map of concept name (lowercased, underscore) to its value and version
        facts_map = {}
        input_versions = {}
        for fact, version in results:
            concept_key = fact.concept.lower().replace(" ", "_")
            facts_map[concept_key] = version.value
            input_versions[fact.concept] = version.version

        # Extract values
        ebitda = facts_map.get("ebitda")
        revenue = facts_map.get("revenue")
        total_debt = facts_map.get("total_debt")
        cash = facts_map.get("cash")
        interest_expense = facts_map.get("interest_expense")

        # 3. Calculate derived metrics
        derived_values = {}

        # Net Debt = Total Debt - Cash
        net_debt = None
        if total_debt is not None and cash is not None:
            net_debt = calculate_net_debt(total_debt, cash)
            derived_values["net_debt"] = net_debt

        # Net Debt / EBITDA
        if net_debt is not None and ebitda is not None and ebitda != 0:
            val = calculate_net_debt_to_ebitda(net_debt, ebitda)
            import math
            if not math.isnan(val):
                derived_values["net_debt_to_ebitda"] = val

        # EBITDA Margin = EBITDA / Revenue
        if ebitda is not None and revenue is not None and revenue != 0:
            val = calculate_ebitda_margin(ebitda, revenue)
            import math
            if not math.isnan(val):
                derived_values["ebitda_margin"] = val

        # Interest Coverage = EBITDA / Interest Expense
        if ebitda is not None and interest_expense is not None and interest_expense != 0:
            val = calculate_interest_coverage(ebitda, interest_expense)
            import math
            if not math.isnan(val):
                derived_values["interest_coverage"] = val

        # 4. Save or update calculated values in db
        version_str = json.dumps(input_versions)
        for metric_name, value in derived_values.items():
            existing = db_session.query(DerivedMetricValue).filter(
                DerivedMetricValue.company_id == company_id,
                DerivedMetricValue.metric_name == metric_name,
                DerivedMetricValue.fiscal_year == year,
                DerivedMetricValue.fiscal_period == period
            ).first()

            if existing:
                existing.value = value
                existing.calculated_at = datetime.utcnow()
                existing.input_fact_versions = version_str
                existing.calculation_version = "1.0"
            else:
                new_metric = DerivedMetricValue(
                    company_id=company_id,
                    metric_name=metric_name,
                    value=value,
                    fiscal_year=year,
                    fiscal_period=period,
                    calculated_at=datetime.utcnow(),
                    calculation_version="1.0",
                    input_fact_versions=version_str
                )
                db_session.add(new_metric)

        try:
            db_session.commit()
            logger.info("Successfully updated derived metrics snapshots in database.")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to commit derived metrics: {e}")
            raise e
