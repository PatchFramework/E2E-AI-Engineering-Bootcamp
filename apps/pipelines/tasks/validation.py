import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models.db_models import FinancialFact, FinancialFactVersion, DataQualityIssue, Document, SourceLocation

logger = logging.getLogger("pipelines.tasks.validation")


def validate_facts(extraction_result: Dict[str, Any], db_session: Optional[Session] = None) -> Dict[str, Any]:
    """
    Performs mathematical consistency, financial sanity, and prior-year reconciliation checks.
    Logs warnings/errors as unresolved DataQualityIssue database records.
    """
    document_id = extraction_result["document_id"]
    company_id = extraction_result["company_id"]
    target_year = extraction_result["fiscal_year"]
    target_period = extraction_result["fiscal_period"]
    
    logger.info(f"Starting accounting validation task for document_id {document_id}")
    
    db = db_session if db_session is not None else SessionLocal()
    try:
        # 1. Fetch all current active facts for this company (both target period and historical)
        results = db.query(FinancialFact, FinancialFactVersion).join(
            FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
        ).filter(
            FinancialFact.company_id == company_id,
            FinancialFactVersion.is_current == True
        ).all()
        
        # Organize facts by (year, period) -> concept (lowercased) -> version value
        facts_grid = {}
        for fact, version in results:
            key = (fact.fiscal_year, fact.fiscal_period)
            if key not in facts_grid:
                facts_grid[key] = {}
            concept_key = fact.concept.lower().replace(" ", "_").replace("-", "_")
            facts_grid[key][concept_key] = {
                "value": version.value,
                "fact_id": fact.id,
                "version_id": version.id
            }

        # Clear out any previous unresolved quality issues for this document
        db.query(DataQualityIssue).filter(
            DataQualityIssue.document_id == document_id,
            DataQualityIssue.is_resolved == False
        ).delete()
        db.commit()

        # 2. Check Mathematical Constraints for target period
        target_key = (target_year, target_period)
        if target_key in facts_grid:
            period_facts = facts_grid[target_key]
            
            # Helper to get value safely
            def get_val(concept_name: str) -> Optional[float]:
                norm = concept_name.lower().replace(" ", "_").replace("-", "_")
                entry = period_facts.get(norm)
                return entry["value"] if entry is not None else None

            rev = get_val("revenue")
            cogs = get_val("cost_of_goods_sold")
            gp = get_val("gross_profit")
            opex = get_val("operating_expense")
            opinc = get_val("operating_income") or get_val("ebit")
            assets = get_val("total_assets")
            liab = get_val("total_liabilities")
            equity = get_val("total_equity") or get_val("equity")
            cur_assets = get_val("current_assets")
            cur_liab = get_val("current_liabilities")
            working_cap = get_val("working_capital") or get_val("net_working_capital")
            ocf = get_val("operating_cash_flow")
            capex = get_val("capital_expenditures") or get_val("capex")
            fcf = get_val("free_cash_flow")
            tot_debt = get_val("total_debt")
            st_debt = get_val("short_term_debt")
            lt_debt = get_val("long_term_debt")
            cash = get_val("cash")

            # Check 1: Gross Profit = Revenue - COGS
            if gp is not None and rev is not None and cogs is not None:
                expected_gp = rev - cogs
                if abs(gp - expected_gp) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Gross Profit",
                        message=(
                            f"Mathematical discrepancy: Gross Profit ({gp}) does not equal "
                            f"Revenue ({rev}) - Cost of Goods Sold ({cogs}). Expected {expected_gp}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # Check 2: Operating Income = Gross Profit - Operating Expense
            if opinc is not None and gp is not None and opex is not None:
                expected_opinc = gp - opex
                if abs(opinc - expected_opinc) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Operating Income",
                        message=(
                            f"Mathematical discrepancy: Operating Income ({opinc}) does not equal "
                            f"Gross Profit ({gp}) - Operating Expense ({opex}). Expected {expected_opinc}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # Check 3: Total Assets = Total Liabilities + Total Equity
            if assets is not None and liab is not None and equity is not None:
                expected_assets = liab + equity
                if abs(assets - expected_assets) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Total Assets",
                        message=(
                            f"Mathematical discrepancy: Total Assets ({assets}) does not equal "
                            f"Total Liabilities ({liab}) + Total Equity ({equity}). Expected {expected_assets}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # Check 4: Free Cash Flow = Operating Cash Flow - Capex
            if fcf is not None and ocf is not None and capex is not None:
                expected_fcf = ocf - capex
                if abs(fcf - expected_fcf) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Free Cash Flow",
                        message=(
                            f"Mathematical discrepancy: Free Cash Flow ({fcf}) does not equal "
                            f"Operating Cash Flow ({ocf}) - Capital Expenditures ({capex}). Expected {expected_fcf}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # Check 5: Total Debt = Short-term Debt + Long-term Debt
            if tot_debt is not None and st_debt is not None and lt_debt is not None:
                expected_debt = st_debt + lt_debt
                if abs(tot_debt - expected_debt) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Total Debt",
                        message=(
                            f"Mathematical discrepancy: Total Debt ({tot_debt}) does not equal "
                            f"Short-term Debt ({st_debt}) + Long-term Debt ({lt_debt}). Expected {expected_debt}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # Check 6: Working Capital = Current Assets - Current Liabilities
            if working_cap is not None and cur_assets is not None and cur_liab is not None:
                expected_wc = cur_assets - cur_liab
                if abs(working_cap - expected_wc) > 1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="ACCOUNTING_RULE_VIOLATION",
                        severity="ERROR",
                        concept="Working Capital",
                        message=(
                            f"Mathematical discrepancy: Working Capital ({working_cap}) does not equal "
                            f"Current Assets ({cur_assets}) - Current Liabilities ({cur_liab}). Expected {expected_wc}."
                        ),
                        is_resolved=False
                    )
                    db.add(issue)

            # ---------------- Financial Sanity Checks ----------------
            if rev is not None and rev < 0:
                issue = DataQualityIssue(
                    company_id=company_id,
                    document_id=document_id,
                    issue_type="SANITY_CHECK_WARNING",
                    severity="WARNING",
                    concept="Revenue",
                    message=f"Financial sanity warning: Revenue is reported as a negative value ({rev}).",
                    is_resolved=False
                )
                db.add(issue)

            if cash is not None and cash < 0:
                issue = DataQualityIssue(
                    company_id=company_id,
                    document_id=document_id,
                    issue_type="SANITY_CHECK_WARNING",
                    severity="WARNING",
                    concept="Cash",
                    message=f"Financial sanity warning: Cash balance is reported as negative ({cash}).",
                    is_resolved=False
                )
                db.add(issue)

            if assets is not None and assets < 0:
                issue = DataQualityIssue(
                    company_id=company_id,
                    document_id=document_id,
                    issue_type="SANITY_CHECK_WARNING",
                    severity="WARNING",
                    concept="Total Assets",
                    message=f"Financial sanity warning: Total Assets is reported as negative ({assets}).",
                    is_resolved=False
                )
                db.add(issue)

            if tot_debt is not None and tot_debt < 0:
                issue = DataQualityIssue(
                    company_id=company_id,
                    document_id=document_id,
                    issue_type="SANITY_CHECK_WARNING",
                    severity="WARNING",
                    concept="Total Debt",
                    message=f"Financial sanity warning: Total Debt is reported as negative ({tot_debt}).",
                    is_resolved=False
                )
                db.add(issue)

            if gp is not None and rev is not None and rev > 0:
                gm = gp / rev
                if gm > 1.0 or gm < -1.0:
                    issue = DataQualityIssue(
                        company_id=company_id,
                        document_id=document_id,
                        issue_type="SANITY_CHECK_WARNING",
                        severity="WARNING",
                        concept="Gross Profit",
                        message=f"Financial sanity warning: Gross Margin ({gm*100:.1f}%) is outside the realistic range [-100%, 100%].",
                        is_resolved=False
                    )
                    db.add(issue)

        # 3. Check Prior-Year Reconciliation
        for (year, period), period_facts in facts_grid.items():
            if year < target_year:
                for concept_key, new_entry in period_facts.items():
                    old_versions = db.query(FinancialFactVersion).filter(
                        FinancialFactVersion.fact_id == new_entry["fact_id"],
                        FinancialFactVersion.id != new_entry["version_id"]
                    ).all()
                    
                    for old_v in old_versions:
                        if old_v.source_location_id:
                            old_source_loc = db.query(SourceLocation).filter(SourceLocation.id == old_v.source_location_id).first()
                            if old_source_loc and old_source_loc.document_id != document_id:
                                if abs(old_v.value - new_entry["value"]) > 1.0:
                                    concept_display = concept_key.replace("_", " ").title()
                                    issue = DataQualityIssue(
                                        company_id=company_id,
                                        document_id=document_id,
                                        issue_type="RECONCILIATION_DISCREPANCY",
                                        severity="WARNING",
                                        concept=concept_display,
                                        message=(
                                            f"Prior-year reconciliation failure: Concept '{concept_display}' for "
                                            f"FY{year} ({period}) is reported as {new_entry['value']} in the current document, "
                                            f"but exists in the workstation database as {old_v.value}."
                                        ),
                                        is_resolved=False
                                    )
                                    db.add(issue)
                                    break

        db.commit()
        logger.info("Accounting validation complete.")
        return {"status": "success", "document_id": document_id}
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Error during facts validation: {e}")
        raise e
    finally:
        if db_session is None:
            db.close()
