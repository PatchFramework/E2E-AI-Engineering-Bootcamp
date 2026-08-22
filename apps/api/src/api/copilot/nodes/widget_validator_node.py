import time
import logging
from typing import Dict, Any, List

from pydantic import ValidationError
from api.copilot.state import CopilotGraphState, CleanEvent
from api.copilot.schemas.widget_schemas import (
    LineChartSpec, BarChartSpec, PieChartSpec, WordCloudSpec, TableWidgetSpec
)
from api.copilot.tools.widget_tools import build_fallback_table_spec

logger = logging.getLogger(__name__)

def validate_widget_node(state: CopilotGraphState) -> Dict[str, Any]:
    """
    Validates pending_widget candidate against strict Pydantic schemas.
    Enforces a 3-retry self-correction limit, after which it falls back to a TableWidgetSpec.
    Appends validated widget event to clean_event_history.
    """
    pending = state.get("pending_widget")
    if not pending:
        return {"pending_widget": None, "widget_validation_error": None}

    retries = state.get("widget_validation_retries", 0)
    w_type = pending.get("widgetType")
    c_type = pending.get("chartType")
    new_events: List[CleanEvent] = []

    try:
        if w_type == "word_cloud":
            WordCloudSpec(**pending)
        elif w_type == "chart" and c_type == "line":
            LineChartSpec(**pending)
        elif w_type == "chart" and c_type == "bar":
            BarChartSpec(**pending)
        elif w_type == "chart" and c_type == "pie":
            PieChartSpec(**pending)
        elif w_type == "table":
            TableWidgetSpec(**pending)
        else:
            raise ValueError(f"Unsupported widget type: '{w_type}' (chartType: '{c_type}')")

        logger.info(f"Widget schema validation PASSED for '{pending.get('title')}'.")
        new_events.append({
            "event_type": "GEN_UI_SPEC",
            "agent": "gen_ui",
            "content": f"Validated {w_type} widget ({pending.get('title')})",
            "metadata": {"widget": pending},
            "timestamp": time.time()
        })

        return {
            "pending_widget": pending,
            "widget_validation_error": None,
            "clean_event_history": new_events,
            "reasoning_status": "Validated Generative UI chart schema"
        }
    except (ValidationError, ValueError) as err:
        err_msg = str(err)
        logger.warning(f"Widget schema validation failed (attempt {retries + 1}/3): {err_msg}")

        if retries < 2:  # 0, 1 -> retry (total 3 attempts)
            return {
                "widget_validation_retries": retries + 1,
                "widget_validation_error": err_msg,
                "reasoning_status": f"Refining chart widget schema (retry {retries + 1}/3)..."
            }
        else:
            # 3 retries exhausted -> fallback to TableWidgetSpec
            logger.info("Max widget validation retries reached. Degraded to TableWidgetSpec fallback.")
            raw_data = pending.get("data") or pending.get("wordCloudData") or []
            fallback = build_fallback_table_spec(
                title=pending.get("title", "Financial Data Table"),
                raw_data=raw_data if isinstance(raw_data, list) else [],
                description="Raw Data Table (Automatic fallback after chart validation limit)"
            )
            fallback_dict = fallback.model_dump()
            new_events.append({
                "event_type": "GEN_UI_SPEC",
                "agent": "gen_ui",
                "content": f"Fallback table widget generated: {fallback.title}",
                "metadata": {"widget": fallback_dict},
                "timestamp": time.time()
            })

            return {
                "pending_widget": fallback_dict,
                "widget_validation_retries": 3,
                "widget_validation_error": None,
                "clean_event_history": new_events,
                "reasoning_status": "Generated fallback data table widget"
            }

