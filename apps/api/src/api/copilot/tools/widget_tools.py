from typing import Dict, Any, List, Optional, Literal
from api.copilot.schemas.widget_schemas import (
    LineChartSpec, BarChartSpec, PieChartSpec, WordCloudSpec, TableWidgetSpec, ChartSeriesConfig, ChartWidgetPayload
)
from langsmith import traceable
from langchain_core.tools import tool

def build_line_chart_spec_impl(
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

def build_bar_chart_spec_impl(
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

def build_pie_chart_spec_impl(
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

def build_word_cloud_spec_impl(
    title: str,
    word_cloud_data: List[Dict[str, Any]],
    description: Optional[str] = None
) -> WordCloudSpec:
    return WordCloudSpec(
        title=title,
        description=description,
        wordCloudData=word_cloud_data
    )

def build_fallback_table_spec_impl(
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

@tool
@traceable(name="build_line_chart_spec", run_type="tool")
def build_line_chart_spec(
    title: str,
    series: List[Dict[str, str]],
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> LineChartSpec:
    """Builds a structured LineChartSpec from raw time series data and series configuration."""
    return build_line_chart_spec_impl(title, series, data, description, unit)

@tool
@traceable(name="build_bar_chart_spec", run_type="tool")
def build_bar_chart_spec(
    title: str,
    series: List[Dict[str, str]],
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> BarChartSpec:
    """Builds a structured BarChartSpec from comparison data and series configuration."""
    return build_bar_chart_spec_impl(title, series, data, description, unit)

@tool
@traceable(name="build_pie_chart_spec", run_type="tool")
def build_pie_chart_spec(
    title: str,
    data: List[Dict[str, Any]],
    description: Optional[str] = None,
    unit: Optional[str] = None
) -> PieChartSpec:
    """Builds a structured PieChartSpec from component breakdown data."""
    return build_pie_chart_spec_impl(title, data, description, unit)

@tool
@traceable(name="build_word_cloud_spec", run_type="tool")
def build_word_cloud_spec(
    title: str,
    word_cloud_data: List[Dict[str, Any]],
    description: Optional[str] = None
) -> WordCloudSpec:
    """Builds a structured WordCloudSpec from word frequency data."""
    return build_word_cloud_spec_impl(title, word_cloud_data, description)

@tool
@traceable(name="build_fallback_table_spec", run_type="tool")
def build_fallback_table_spec(
    title: str,
    raw_data: List[Dict[str, Any]],
    description: Optional[str] = "Data Table (Chart validation limit reached)"
) -> TableWidgetSpec:
    """Builds a fallback TableWidgetSpec when chart validation fails."""
    return build_fallback_table_spec_impl(title, raw_data, description)

def create_widget_tools():
    """Returns the list of Generative UI chart construction tools for LLM tool binding."""
    return [
        build_line_chart_spec,
        build_bar_chart_spec,
        build_pie_chart_spec,
        build_word_cloud_spec
    ]

