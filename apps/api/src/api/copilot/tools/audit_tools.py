import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from api.models.db_models import (
    FinancialFact, FinancialFactVersion, DataQualityIssue, AuditEvent
)

logger = logging.getLogger(__name__)

def get_unverified_facts(db: Session, company_id: int) -> Dict[str, Any]:
    """
    Fetches all financial facts for a company that have not yet been verified by a human analyst.
    """
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
        "company_id": company_id,
        "unverified_count": len(unverified_list),
        "facts": unverified_list
    }

def get_data_quality_issues(db: Session, company_id: int) -> Dict[str, Any]:
    """
    Fetches accounting discrepancies, balance check mismatches, and reconciliation issues.
    """
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
        "company_id": company_id,
        "active_issues_count": len(issue_list),
        "issues": issue_list
    }

def get_fact_audit_trail(db: Session, fact_id: int) -> Dict[str, Any]:
    """
    Fetches the bi-temporal audit log and modification history for a specific financial fact.
    """
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
        "fact_id": fact_id,
        "event_count": len(event_list),
        "audit_events": event_list
    }
