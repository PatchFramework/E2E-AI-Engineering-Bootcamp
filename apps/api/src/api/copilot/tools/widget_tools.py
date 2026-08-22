from typing import Dict, Any, List, Optional, Literal
from api.copilot.schemas.widget_schemas import (
    LineChartSpec, BarChartSpec, PieChartSpec, WordCloudSpec, TableWidgetSpec, ChartSeriesConfig, ChartWidgetPayload
)
from langsmith import traceable, get_current_run_tree
from langchain_core.tools import tool

@tool
@traceable(
    name="build_line_chart_spec",
    run_type="tool",
    metadata={
        "description": "Builds a structured LineChartSpec from raw data and series configuration.",
        "input": ["title", "series", "data"],
        "output": ["LineChartSpec"]
    }
)
def build_line_chart_spec(
    title: str,
    series: List[Dict[str, str]],
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> LineChartSpec:
    parsed_series = [ChartSeriesConfig(**s) for s in series]
    return LineChartSpec(
        title=title,
        description=description,
        series=parsed_series,
        data=data,
        unit=unit
    )

@tool
@traceable(
    name="build_bar_chart_spec",
    run_type="tool",
    metadata={
        "description": "Builds a structured BarChartSpec from raw data and series configuration.",
        "input": ["title", "series", "data"],
        "output": ["BarChartSpec"]
    }
)
def build_bar_chart_spec(
    title: str,
    series: List[Dict[str, str]],
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> BarChartSpec:
    parsed_series = [ChartSeriesConfig(**s) for s in series]
    return BarChartSpec(
        title=title,
        description=description,
        series=parsed_series,
        data=data,
        unit=unit
    )


@tool
@traceable(
    name="build_pie_chart_spec",
    run_type="tool",
    metadata={
        "description": "Builds a structured PieChartSpec from raw data.",
        "input": ["title", "data"],
        "output": ["PieChartSpec"]
    }
)
def build_pie_chart_spec(
    title: str,
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> PieChartSpec:
    return PieChartSpec(
        title=title,
        description=description,
        data=data,
        unit=unit
    )


@tool
@traceable(
    name="build_word_cloud_spec",
    run_type="tool",
    metadata={
        "description": "Builds a structured WordCloudSpec from word frequency data.",
        "input": ["title", "word_cloud_data"],
        "output": ["WordCloudSpec"]
    }
)
def build_word_cloud_spec(
    title: str,
    word_cloud_data: List[Dict[str, Any]],
    description: Optional[str] = None
) -> WordCloudSpec:
    return WordCloudSpec(
        title=title,
        description=description,
        wordCloudData=word_cloud_data
    )


@tool
@traceable(
    name="build_fallback_table_spec",
    run_type="tool",
    metadata={
        "description": "Builds a fallback TableWidgetSpec when chart validation fails.",
        "input": ["title", "raw_data"],
        "output": ["TableWidgetSpec"]
    }
)
def build_fallback_table_spec(
    title: str,
    raw_data: List[Dict[str, Any]],
    description: Optional[str] = "Data Table (Chart validation limit reached)"
) -> TableWidgetSpec:
    columns = list(raw_data[0].keys()) if raw_data else []
    return TableWidgetSpec(
        title=title,
        description=description,
        columns=columns,
        rows=raw_data
    )
