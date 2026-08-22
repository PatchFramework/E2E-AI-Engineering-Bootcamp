import ast
import operator
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from langsmith import traceable
from langchain_core.tools import tool, BaseTool

from api.models.db_models import (
    DerivedMetricValue, DerivedMetricDefinition, FinancialFact, FinancialFactVersion, SourceLocation, Document
)
from api.core.metric_registry import METRIC_REGISTRY
from api.services.metric_calculation import MetricCalculationService
from api.copilot.schemas.citation_schemas import CitationSource

logger = logging.getLogger(__name__)

# Safe AST Arithmetic Evaluator
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _eval_ast_node(node: ast.AST, variables: Dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    elif isinstance(node, ast.Name):
        if node.id in variables:
            return float(variables[node.id])
        raise ValueError(f"Unknown variable in formula: '{node.id}'. Available variables: {list(variables.keys())}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[op_type](_eval_ast_node(node.operand, variables))
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            left = _eval_ast_node(node.left, variables)
            right = _eval_ast_node(node.right, variables)
            if op_type == ast.Div and right == 0:
                raise ZeroDivisionError("Division by zero in formula evaluation")
            return _SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type}")
    else:
        raise ValueError(f"Unsupported AST expression: {type(node)}")


@tool
@traceable(name="evaluate_formula", run_type="tool")
def evaluate_formula(expression: str, variables: Dict[str, float]) -> Dict[str, Any]:
    """
    Deterministically evaluates a mathematical formula expression using Python's AST.
    Guarantees safe arithmetic without arbitrary code execution.
    """
    try:
        cleaned_expr = expression.replace("^", "**") # normalize power if any
        parsed = ast.parse(cleaned_expr, mode='eval')
        result = _eval_ast_node(parsed.body, variables)
        return {
            "status": "SUCCESS",
            "expression": expression,
            "variables": variables,
            "result": round(result, 4)
        }
    except Exception as e:
        logger.warning(f"Formula evaluation error for '{expression}': {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggestion": "Verify variable names against financial facts and ensure non-zero divisors."
        }

def get_company_metrics_impl(db: Session, company_id: int, fiscal_year: Optional[int] = None) -> Dict[str, Any]:
    """Internal implementation for get_company_metrics."""
    try:
        if fiscal_year is None:
            latest_metric = db.query(DerivedMetricValue).filter(
                DerivedMetricValue.company_id == company_id
            ).order_by(DerivedMetricValue.fiscal_year.desc()).first()
            fiscal_year = latest_metric.fiscal_year if latest_metric else 2025

        records = db.query(DerivedMetricValue).filter(
            DerivedMetricValue.company_id == company_id,
            DerivedMetricValue.fiscal_year == fiscal_year
        ).all()

        metrics_summary = {}
        for r in records:
            cfg = METRIC_REGISTRY.get(r.metric_name)
            metrics_summary[r.metric_name] = {
                "display_name": cfg.display_name if cfg else r.metric_name,
                "category": cfg.category if cfg else "Other",
                "value": r.value,
                "unit": cfg.unit if cfg else "ratio",
                "status": r.status,
                "fiscal_year": r.fiscal_year,
                "fiscal_period": r.fiscal_period,
                "status_reason": r.status_reason
            }

        return {
            "status": "SUCCESS",
            "company_id": company_id,
            "fiscal_year": fiscal_year,
            "metrics_count": len(metrics_summary),
            "metrics": metrics_summary
        }
    except Exception as e:
        logger.exception(f"Error fetching company metrics: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggestion": "Verify the company_id and fiscal_year parameters."
        }

def get_metric_history_impl(db: Session, company_id: int, metric_name: str) -> Dict[str, Any]:
    """Internal implementation for get_metric_history."""
    try:
        records = db.query(DerivedMetricValue).filter(
            DerivedMetricValue.company_id == company_id,
            DerivedMetricValue.metric_name == metric_name
        ).order_by(DerivedMetricValue.fiscal_year.asc()).all()

        history = [
            {
                "fiscal_year": r.fiscal_year,
                "fiscal_period": r.fiscal_period,
                "value": r.value,
                "status": r.status
            }
            for r in records
        ]

        cfg = METRIC_REGISTRY.get(metric_name)
        return {
            "status": "SUCCESS",
            "company_id": company_id,
            "metric_name": metric_name,
            "display_name": cfg.display_name if cfg else metric_name,
            "unit": cfg.unit if cfg else "ratio",
            "history": history,
            "history_count": len(history)
        }
    except Exception as e:
        logger.exception(f"Error fetching metric history for {metric_name}: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggestion": "Check valid metric names e.g. 'net_debt_to_ebitda', 'ebitda_margin', 'current_ratio'."
        }

def get_fact_lineage_impl(db: Session, company_id: int, metric_name: str, fiscal_year: int) -> Dict[str, Any]:
    """Internal implementation for get_fact_lineage."""
    try:
        metric_record = db.query(DerivedMetricValue).filter(
            DerivedMetricValue.company_id == company_id,
            DerivedMetricValue.metric_name == metric_name,
            DerivedMetricValue.fiscal_year == fiscal_year
        ).first()

        if not metric_record:
            return {
                "status": "NOT_FOUND",
                "message": f"No calculated record found for {metric_name} in FY{fiscal_year}",
                "citations": []
            }

        lineage_data = MetricCalculationService.get_metric_lineage(db, metric_record.id)
        citations: List[CitationSource] = []

        if lineage_data and lineage_data.input_facts:
            for f in lineage_data.input_facts:
                src = f.source_location
                doc_id = src.document_id if src else (f.document_id or 1)
                filename = f.document_filename or f"FY{fiscal_year}_Filing.pdf"
                page_num = src.page_number if src else 1
                disp_page = src.displayed_page_number if (src and src.displayed_page_number) else f"p. {page_num}"
                bbox = src.bounding_box if src else None
                snippet = src.text_snippet if src else f"{f.concept_name}: {f.value} {f.unit}"

                citations.append(CitationSource(
                    document_id=doc_id,
                    filename=filename,
                    page_number=page_num,
                    displayed_page=disp_page,
                    section=src.section_path if src else None,
                    snippet=snippet,
                    bounding_box=bbox,
                    source_type="STRUCTURED_FACT"
                ))

        return {
            "status": "SUCCESS",
            "metric_name": metric_name,
            "fiscal_year": fiscal_year,
            "value": metric_record.value,
            "metric_status": metric_record.status,
            "lineage": lineage_data.model_dump() if lineage_data else {},
            "citations": [c.model_dump() for c in citations]
        }
    except Exception as e:
        logger.exception(f"Error fetching fact lineage: {e}")
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "citations": []
        }

# Direct helper signatures
def get_company_metrics(db: Session, company_id: int, fiscal_year: Optional[int] = None) -> Dict[str, Any]:
    return get_company_metrics_impl(db, company_id, fiscal_year)

def get_metric_history(db: Session, company_id: int, metric_name: str) -> Dict[str, Any]:
    return get_metric_history_impl(db, company_id, metric_name)

def get_fact_lineage(db: Session, company_id: int, metric_name: str, fiscal_year: int) -> Dict[str, Any]:
    return get_fact_lineage_impl(db, company_id, metric_name, fiscal_year)

def create_metric_tools(db: Session) -> List[BaseTool]:
    """
    Creates a list of LangChain @tool objects with `db` session bound via closure.
    The resulting schemas match the LLM argument requirements without exposing `db`.
    """
    @tool
    @traceable(name="get_company_metrics", run_type="tool")
    def get_company_metrics_tool(company_id: int, fiscal_year: Optional[int] = None) -> Dict[str, Any]:
        """Fetches all calculated derived metrics for a company across all 6 financial categories for a fiscal year."""
        return get_company_metrics_impl(db, company_id, fiscal_year)

    @tool
    @traceable(name="get_metric_history", run_type="tool")
    def get_metric_history_tool(company_id: int, metric_name: str) -> Dict[str, Any]:
        """Fetches multi-year historical time series for a single financial credit metric."""
        return get_metric_history_impl(db, company_id, metric_name)

    @tool
    @traceable(name="get_fact_lineage", run_type="tool")
    def get_fact_lineage_tool(company_id: int, metric_name: str, fiscal_year: int) -> Dict[str, Any]:
        """Resolves the exact constituent facts, formulas, and bounding-box citations for a derived KPI."""
        return get_fact_lineage_impl(db, company_id, metric_name, fiscal_year)

    return [
        evaluate_formula,
        get_company_metrics_tool,
        get_metric_history_tool,
        get_fact_lineage_tool
    ]
    