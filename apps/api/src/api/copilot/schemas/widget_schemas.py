from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, model_validator

class ChartSeriesConfig(BaseModel):
    key: str = Field(..., description="Data object key corresponding to this series (e.g., 'leverage', 'ebitda')")
    label: Optional[str] = Field(None, description="Human-readable series name for legend and tooltips")
    name: Optional[str] = Field(None, description="Alternative alias for label")
    color: Optional[str] = Field(None, description="Hex color code (e.g., '#f43f5e', '#10b981')")

    @model_validator(mode="after")
    def populate_label(self) -> 'ChartSeriesConfig':
        if not self.label and self.name:
            self.label = self.name
        elif not self.label:
            self.label = self.key
        return self

class LineChartSpec(BaseModel):
    widgetType: Literal["chart"] = "chart"
    chartType: Literal["line"] = "line"
    title: str = Field(..., description="Chart title")
    description: Optional[str] = Field(None, description="Subtitle or explanation")
    series: List[ChartSeriesConfig] = Field(..., min_length=1, description="List of data series to plot")
    data: List[Dict[str, Any]] = Field(..., min_length=1, description="Array of data point objects containing time keys and series keys")
    unit: Optional[str] = Field(None, description="Measurement unit (e.g., 'x', '%', 'EUR M')")

    @model_validator(mode="after")
    def validate_series_keys(self) -> 'LineChartSpec':
        series_keys = {s.key for s in self.series}
        for idx, row in enumerate(self.data):
            row_keys = set(row.keys())
            matched = series_keys.intersection(row_keys)
            if not matched:
                raise ValueError(
                    f"Data row {idx} {row} does not contain any matching series keys ({series_keys}). "
                    f"Ensure data item keys match series 'key' fields."
                )
        return self

class BarChartSpec(BaseModel):
    widgetType: Literal["chart"] = "chart"
    chartType: Literal["bar"] = "bar"
    title: str = Field(..., description="Chart title")
    description: Optional[str] = Field(None, description="Subtitle or explanation")
    series: List[ChartSeriesConfig] = Field(..., min_length=1, description="List of data series for bars")
    data: List[Dict[str, Any]] = Field(..., min_length=1, description="Array of data point objects")
    unit: Optional[str] = Field(None, description="Measurement unit")

    @model_validator(mode="after")
    def validate_series_keys(self) -> 'BarChartSpec':
        series_keys = {s.key for s in self.series}
        for idx, row in enumerate(self.data):
            row_keys = set(row.keys())
            if not series_keys.intersection(row_keys):
                raise ValueError(
                    f"Data row {idx} {row} does not contain any matching series keys ({series_keys})."
                )
        return self

class PieChartSpec(BaseModel):
    widgetType: Literal["chart"] = "chart"
    chartType: Literal["pie"] = "pie"
    title: str = Field(..., description="Chart title")
    description: Optional[str] = Field(None, description="Subtitle or explanation")
    data: List[Dict[str, Any]] = Field(..., min_length=1, description="Array of slices with 'name' and positive 'value'")
    unit: Optional[str] = Field(None, description="Measurement unit")

    @model_validator(mode="after")
    def validate_pie_data(self) -> 'PieChartSpec':
        for idx, item in enumerate(self.data):
            if "name" not in item or "value" not in item:
                raise ValueError(f"Pie slice {idx} {item} must contain both 'name' (string) and 'value' (number).")
            try:
                val = float(item["value"])
                if val < 0:
                    raise ValueError(f"Pie slice '{item.get('name')}' has negative value {val}. Pie values must be non-negative.")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid numeric value in pie slice {idx}: {e}")
        return self

class WordCloudItem(BaseModel):
    text: str = Field(..., description="Term or concept keyword")
    value: int = Field(..., ge=1, description="Occurrence count or weight")

class WordCloudSpec(BaseModel):
    widgetType: Literal["word_cloud"] = "word_cloud"
    title: str = Field(..., description="Word cloud title")
    description: Optional[str] = Field(None, description="Subtitle or explanation")
    wordCloudData: List[WordCloudItem] = Field(..., min_length=1, description="Array of term-frequency objects")

class TableWidgetSpec(BaseModel):
    widgetType: Literal["table"] = "table"
    title: str = Field(..., description="Table title")
    description: Optional[str] = Field(None, description="Subtitle or fallback explanation")
    columns: List[str] = Field(default_factory=list, description="Column headers")
    rows: List[Dict[str, Any]] = Field(..., description="Array of row data")

ChartWidgetPayload = Union[LineChartSpec, BarChartSpec, PieChartSpec, WordCloudSpec, TableWidgetSpec]
