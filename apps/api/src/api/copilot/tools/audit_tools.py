import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langsmith import traceable
from langchain_core.tools import tool, BaseTool

from api.models.db_models import (
    FinancialFact, FinancialFactVersion, DataQualityIssue, AuditEvent
)

logger = logging.getLogger(__name__)

def get_unverified_facts_impl(db: Session, company_id: int) -> Dict[str, Any]:
    """Internal implementation for get_unverified_facts."""
    try:
        records = db.query(FinancialFact, FinancialFactVersion).join(
            FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
        ).filter(
            FinancialFact.company_id == company_id,
            FinancialFactVersion.is_current == True,
            FinancialFactVersion.verification_status != "VERIFIED"
        ).all()

        unverified_list = [
            {
                "fact_id": fact.id,
                "concept": fact.concept,
                "value": ver.value,
                "unit": ver.unit,
                "fiscal_year": fact.fiscal_year,
                "fiscal_period": fact.fiscal_period,
                "origin": ver.origin,
                "verification_status": ver.verification_status
            }
            for (fact, ver) in records
        ]

        return {
            "status": "SUCCESS",
            "company_id": company_id,
            "unverified_count": len(unverified_list),
            "facts": unverified_list
        }
    except Exception as e:
        logger.exception(f"Error fetching unverified facts: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "unverified_count": 0,
            "facts": []
        }

def get_data_quality_issues_impl(db: Session, company_id: int) -> Dict[str, Any]:
    """Internal implementation for get_data_quality_issues."""
    try:
        issues = db.query(DataQualityIssue).filter(
            DataQualityIssue.company_id == company_id,
            DataQualityIssue.status != "RESOLVED"
        ).all()

        issue_list = [
            {
                "id": issue.id,
                "rule_name": issue.rule_name,
                "severity": issue.severity,
                "message": issue.message,
                "details": issue.details,
                "status": issue.status
            }
            for issue in issues
        ]

        return {
            "status": "SUCCESS",
            "company_id": company_id,
            "active_issues_count": len(issue_list),
            "issues": issue_list
        }
    except Exception as e:
        logger.exception(f"Error fetching data quality issues: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "active_issues_count": 0,
            "issues": []
        }

def get_fact_audit_trail_impl(db: Session, fact_id: int) -> Dict[str, Any]:
    """Internal implementation for get_fact_audit_trail."""
    try:
        events = db.query(AuditEvent).filter(
            AuditEvent.entity_type == "financial_fact",
            AuditEvent.entity_id == fact_id
        ).order_by(AuditEvent.timestamp.asc()).all()

        event_list = [
            {
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "actor": e.actor,
                "action": e.action,
                "previous_value": e.previous_value,
                "new_value": e.new_value,
                "reason": e.reason
            }
            for e in events
        ]

        return {
            "status": "SUCCESS",
            "fact_id": fact_id,
            "event_count": len(event_list),
            "audit_events": event_list
        }
    except Exception as e:
        logger.exception(f"Error fetching fact audit trail for fact_id={fact_id}: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "event_count": 0,
            "audit_events": []
        }


def create_audit_tools(db: Session) -> List[BaseTool]:
    """
    Creates LangChain @tool objects with `db` session bound via closure.
    """
    @tool
    @traceable(name="get_unverified_facts", run_type="tool")
    def get_unverified_facts_tool(company_id: int) -> Dict[str, Any]:
        """Fetches all financial facts for a company that have not yet been verified by a human analyst."""
        return get_unverified_facts_impl(db, company_id)

    @tool
    @traceable(name="get_data_quality_issues", run_type="tool")
    def get_data_quality_issues_tool(company_id: int) -> Dict[str, Any]:
        """Fetches accounting discrepancies, balance check mismatches, and reconciliation issues."""
        return get_data_quality_issues_impl(db, company_id)

    @tool
    @traceable(name="get_fact_audit_trail", run_type="tool")
    def get_fact_audit_trail_tool(fact_id: int) -> Dict[str, Any]:
        """Fetches the bi-temporal audit log and modification history for a specific financial fact."""
        return get_fact_audit_trail_impl(db, fact_id)

    return [
        get_unverified_facts_tool,
        get_data_quality_issues_tool,
        get_fact_audit_trail_tool
    ]