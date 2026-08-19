import logging
import json
import math
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, joinedload

from api.models.db_models import (
    FinancialFact, FinancialFactVersion, SourceLocation, Document, DocumentChunk,
    DerivedMetricDefinition, DerivedMetricValue, DerivedMetricInputFact
)
from api.core.metric_registry import METRIC_REGISTRY, MetricConfig

logger = logging.getLogger("api.services.metric_calculation")


class MetricCalculationService:
    @staticmethod
    def sync_metric_definitions(db_session: Session) -> Dict[str, int]:
        """
        Ensures all metrics defined in METRIC_REGISTRY exist in the `derived_metric_definitions` table.
        Returns a mapping from metric_name to definition_id.
        """
        def_map = {}
        for key, config in METRIC_REGISTRY.items():
            existing = db_session.query(DerivedMetricDefinition).filter(
                DerivedMetricDefinition.metric_name == key
            ).first()

            if existing:
                existing.display_name = config.display_name
                existing.category = config.category
                existing.formula_expression = config.formula_expression
                existing.unit = config.unit
                existing.required_concepts = config.required_concepts
                existing.description = config.description
                def_map[key] = existing.id
            else:
                new_def = DerivedMetricDefinition(
                    metric_name=key,
                    display_name=config.display_name,
                    category=config.category,
                    formula_expression=config.formula_expression,
                    unit=config.unit,
                    required_concepts=config.required_concepts,
                    description=config.description,
                    created_at=datetime.utcnow()
                )
                db_session.add(new_def)
                db_session.flush()
                def_map[key] = new_def.id

        db_session.commit()
        return def_map

    @staticmethod
    def recalculate_metrics_for_period(db_session: Session, company_id: int, year: int, period: str) -> Dict[str, Any]:
        """
        Synchronously fetches current active facts for a given company, year, and period,
        recalculates all derived KPIs across all categories, persists snapshot records
        and establishes relational lineage in `derived_metric_input_facts`.
        """
        logger.info(f"Triggering metric recalculation for company_id={company_id}, year={year}, period={period}")
        
        # 1. Sync metric definitions in DB
        def_map = MetricCalculationService.sync_metric_definitions(db_session)

        # 2. Fetch current active versions of all facts for target period
        current_results = db_session.query(FinancialFact, FinancialFactVersion).join(
            FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
        ).filter(
            FinancialFact.company_id == company_id,
            FinancialFact.fiscal_year == year,
            FinancialFact.fiscal_period == period,
            FinancialFactVersion.is_current == True
        ).all()

        # 3. Fetch prior period facts (for YoY metrics like revenue_growth)
        prior_results = db_session.query(FinancialFact, FinancialFactVersion).join(
            FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
        ).filter(
            FinancialFact.company_id == company_id,
            FinancialFact.fiscal_year == (year - 1),
            FinancialFact.fiscal_period == period,
            FinancialFactVersion.is_current == True
        ).all()

        # Build maps for current period facts
        facts_map: Dict[str, float] = {}
        fact_versions_map: Dict[str, FinancialFactVersion] = {}
        canonical_to_norm: Dict[str, str] = {}

        for fact, version in current_results:
            norm_key = fact.concept.lower().replace(" ", "_").replace("-", "_")
            facts_map[norm_key] = version.value
            fact_versions_map[norm_key] = version
            canonical_to_norm[fact.concept] = norm_key

        # Build maps for prior period facts
        prior_facts_map: Dict[str, float] = {}
        prior_fact_versions_map: Dict[str, FinancialFactVersion] = {}
        for fact, version in prior_results:
            norm_key = fact.concept.lower().replace(" ", "_").replace("-", "_")
            prior_facts_map[norm_key] = version.value
            prior_fact_versions_map[norm_key] = version

        # 4. Iterate over METRIC_REGISTRY and compute each metric
        calculated_count = 0
        unavailable_count = 0

        for metric_name, config in METRIC_REGISTRY.items():
            metric_def_id = def_map.get(metric_name)

            # Check if all required concepts are present
            missing_concepts = []
            used_versions: List[FinancialFactVersion] = []
            used_roles: List[str] = []

            for req_concept in config.required_concepts:
                norm_c = req_concept.lower().replace(" ", "_").replace("-", "_")
                # Also check aliases (e.g. Operating Income / EBIT, Capital Expenditures / Capex)
                found_version = fact_versions_map.get(norm_c)
                if not found_version:
                    if norm_c == "operating_income" and "ebit" in fact_versions_map:
                        found_version = fact_versions_map["ebit"]
                    elif norm_c == "capital_expenditures" and "capex" in fact_versions_map:
                        found_version = fact_versions_map["capex"]
                    elif norm_c == "total_debt" and ("short_term_debt" in fact_versions_map or "long_term_debt" in fact_versions_map):
                        if "short_term_debt" in fact_versions_map:
                            used_versions.append(fact_versions_map["short_term_debt"])
                            used_roles.append("SHORT_TERM_DEBT")
                        if "long_term_debt" in fact_versions_map:
                            used_versions.append(fact_versions_map["long_term_debt"])
                            used_roles.append("LONG_TERM_DEBT")
                        continue

                if found_version:
                    used_versions.append(found_version)
                    used_roles.append("INPUT")
                else:
                    missing_concepts.append(req_concept)

            if config.is_multi_period:
                # Add prior period dependencies
                for req_concept in config.required_concepts:
                    norm_c = req_concept.lower().replace(" ", "_").replace("-", "_")
                    prior_ver = prior_fact_versions_map.get(norm_c)
                    if prior_ver:
                        used_versions.append(prior_ver)
                        used_roles.append("PRIOR_PERIOD")
                    else:
                        missing_concepts.append(f"{req_concept} (FY{year - 1})")

            # Calculate metric value
            val = None
            status = "AVAILABLE"
            status_reason = None

            try:
                if config.compute_fn:
                    raw_val = config.compute_fn(facts_map, prior_facts_map)
                    if raw_val is not None and not math.isnan(raw_val) and not math.isinf(raw_val):
                        val = float(raw_val)
                    else:
                        status = "UNAVAILABLE"
                        if missing_concepts:
                            status_reason = f"Required concept(s) missing: {', '.join(missing_concepts)}"
                        else:
                            status_reason = "Calculation resulted in an undefined or division-by-zero value."
                else:
                    status = "UNAVAILABLE"
                    status_reason = "No computation formula registered."
            except Exception as ex:
                status = "ERROR"
                status_reason = f"Calculation error: {str(ex)}"
                logger.error(f"Error computing metric {metric_name}: {ex}")

            if status == "AVAILABLE":
                calculated_count += 1
            else:
                unavailable_count += 1

            # Prepare lightweight JSON summary for input_fact_versions
            lineage_summary = {
                "metric": metric_name,
                "formula": config.formula_expression,
                "input_versions": {
                    v.fact.concept: v.version for v in used_versions if v.fact
                }
            }

            # 5. Upsert DerivedMetricValue
            derived_metric = db_session.query(DerivedMetricValue).filter(
                DerivedMetricValue.company_id == company_id,
                DerivedMetricValue.metric_name == metric_name,
                DerivedMetricValue.fiscal_year == year,
                DerivedMetricValue.fiscal_period == period
            ).first()

            if derived_metric:
                derived_metric.metric_definition_id = metric_def_id
                derived_metric.value = val
                derived_metric.status = status
                derived_metric.status_reason = status_reason
                derived_metric.calculated_at = datetime.utcnow()
                derived_metric.calculation_version = "2.0"
                derived_metric.input_fact_versions = json.dumps(lineage_summary)
            else:
                derived_metric = DerivedMetricValue(
                    company_id=company_id,
                    metric_definition_id=metric_def_id,
                    metric_name=metric_name,
                    value=val,
                    status=status,
                    status_reason=status_reason,
                    fiscal_year=year,
                    fiscal_period=period,
                    calculated_at=datetime.utcnow(),
                    calculation_version="2.0",
                    input_fact_versions=json.dumps(lineage_summary)
                )
                db_session.add(derived_metric)
                db_session.flush()

            # 6. Establish Relational Lineage in `derived_metric_input_facts`
            # Clear old junction entries for this derived metric
            db_session.query(DerivedMetricInputFact).filter(
                DerivedMetricInputFact.derived_metric_id == derived_metric.id
            ).delete()

            # Insert new junction entries
            for ver, role in zip(used_versions, used_roles):
                concept_name = ver.fact.concept if ver.fact else "Unknown"
                input_fact_link = DerivedMetricInputFact(
                    derived_metric_id=derived_metric.id,
                    fact_version_id=ver.id,
                    concept_name=concept_name,
                    relationship_role=role,
                    created_at=datetime.utcnow()
                )
                db_session.add(input_fact_link)

        db_session.commit()
        logger.info(
            f"Recalculation complete for company {company_id} in {year} {period}. "
            f"Available: {calculated_count}, Unavailable: {unavailable_count}"
        )
        return {
            "status": "success",
            "company_id": company_id,
            "fiscal_year": year,
            "fiscal_period": period,
            "metrics_available": calculated_count,
            "metrics_unavailable": unavailable_count
        }

    @staticmethod
    def get_metric_lineage(db_session: Session, derived_metric_id: int) -> Optional[Dict[str, Any]]:
        """
        Traverses relational foreign keys to assemble full provenance and evidence
        for a calculated metric without data duplication.
        
        Returns:
            - Metric metadata (name, display name, category, formula, value, status)
            - Input facts (fact ID, version, value, unit, concept, verification status)
            - Source locations (document ID, filename, page number, bounding box, text snippet)
            - Citable document chunks matching the source document & page/concept for RAG.
        """
        metric = db_session.query(DerivedMetricValue).options(
            joinedload(DerivedMetricValue.metric_definition),
            joinedload(DerivedMetricValue.input_facts).joinedload(DerivedMetricInputFact.fact_version).joinedload(FinancialFactVersion.fact),
            joinedload(DerivedMetricValue.input_facts).joinedload(DerivedMetricInputFact.fact_version).joinedload(FinancialFactVersion.source_location).joinedload(SourceLocation.document)
        ).filter(DerivedMetricValue.id == derived_metric_id).first()

        if not metric:
            return None

        definition = metric.metric_definition
        inputs_lineage = []
        document_ids = set()
        page_numbers = set()

        for link in metric.input_facts:
            ver = link.fact_version
            fact = ver.fact if ver else None
            loc = ver.source_location if ver else None
            doc = loc.document if loc else None

            if doc:
                document_ids.add(doc.id)
            if loc and loc.page_number:
                page_numbers.add(loc.page_number)

            fact_info = {
                "fact_id": fact.id if fact else None,
                "fact_version_id": ver.id if ver else None,
                "concept": link.concept_name,
                "role": link.relationship_role,
                "value": ver.value if ver else None,
                "unit": ver.unit if ver else "EUR",
                "origin": ver.origin if ver else None,
                "verification_status": ver.verification_status if ver else None,
                "source_location": {
                    "location_id": loc.id if loc else None,
                    "page_number": loc.page_number if loc else None,
                    "displayed_page_number": loc.displayed_page_number if loc else None,
                    "section": loc.section if loc else None,
                    "section_path": loc.section_path if loc else None,
                    "text_snippet": loc.text_snippet if loc else None,
                    "bounding_box": loc.bounding_box if loc else None,
                } if loc else None,
                "document": {
                    "document_id": doc.id if doc else None,
                    "filename": doc.filename if doc else None,
                    "s3_path": doc.s3_path if doc else None,
                    "fiscal_year": doc.fiscal_year if doc else None,
                    "fiscal_period": doc.fiscal_period if doc else None,
                } if doc else None
            }
            inputs_lineage.append(fact_info)

        # Retrieve relevant DocumentChunks for RAG citations
        cited_chunks = []
        if document_ids:
            chunks = db_session.query(DocumentChunk).filter(
                DocumentChunk.document_id.in_(list(document_ids)),
                DocumentChunk.page_number.in_(list(page_numbers)) if page_numbers else True
            ).all()

            for chunk in chunks:
                cited_chunks.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "displayed_page_number": chunk.displayed_page_number,
                    "section_path": chunk.section_path,
                    "text_content": chunk.text_content,
                    "chunk_metadata": chunk.chunk_metadata
                })

        return {
            "derived_metric_id": metric.id,
            "metric_name": metric.metric_name,
            "display_name": definition.display_name if definition else metric.metric_name,
            "category": definition.category if definition else "General",
            "formula_expression": definition.formula_expression if definition else None,
            "value": metric.value,
            "unit": definition.unit if definition else "ratio",
            "status": metric.status,
            "status_reason": metric.status_reason,
            "fiscal_year": metric.fiscal_year,
            "fiscal_period": metric.fiscal_period,
            "calculated_at": metric.calculated_at.isoformat() if metric.calculated_at else None,
            "input_facts": inputs_lineage,
            "cited_chunks": cited_chunks
        }
