import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from api.copilot.state import CopilotGraphState
from api.copilot.tools.audit_tools import (
    get_unverified_facts, get_data_quality_issues, get_fact_audit_trail
)

logger = logging.getLogger(__name__)

def run_data_quality_agent(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    """
    Subagent querying data quality discrepancies, unverified facts, and audit trails.
    """
    company_id = state["company_id"]
    logger.info(f"DataQualityAgent running for company_id={company_id}")

    unverified = get_unverified_facts(db, company_id)
    issues = get_data_quality_issues(db, company_id)

    quality_results = {
        "unverified_facts": unverified,
        "active_issues": issues
    }

    return {
        "quality_issues": quality_results,
        "reasoning_status": f"Audited accounting facts: {issues.get('active_issues_count', 0)} issues, {unverified.get('unverified_count', 0)} unverified"
    }
