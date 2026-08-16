"""
test_dag_structure.py — Tests for the DAG definition in financial_ingestion_dag.py

Validates:
  - The DAG can be imported without errors.
  - All expected tasks exist with correct IDs.
  - The task dependency graph matches the intended topology:
      parse_pdf >> extract_facts >> validate_facts >> calculate_kpis
      parse_pdf >> index_chunks
  - No circular dependencies.
  - The DAG has schedule_interval=None (trigger-only).
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_dag():
    """
    Import and return the DAG object. We must patch Airflow internals that
    attempt DB connections during import, and prevent repeated registration
    in the global DAG bag.
    """
    # Remove cached module so re-imports are fresh between tests if needed
    for key in list(sys.modules.keys()):
        if "financial_ingestion_dag" in key:
            del sys.modules[key]

    import importlib
    dag_module = importlib.import_module("financial_ingestion_dag")
    return dag_module.dag


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDagImport:
    def test_dag_imports_without_error(self):
        """Importing financial_ingestion_dag must not raise any exception."""
        dag = _import_dag()
        assert dag is not None

    def test_dag_id_is_correct(self):
        dag = _import_dag()
        assert dag.dag_id == "financial_ingestion_dag"

    def test_schedule_interval_is_none(self):
        """DAG must be trigger-only (no automatic scheduling)."""
        dag = _import_dag()
        assert dag.schedule_interval is None

    def test_catchup_is_false(self):
        dag = _import_dag()
        assert dag.catchup is False


class TestDagTaskIds:
    def test_all_expected_task_ids_exist(self):
        dag = _import_dag()
        task_ids = {t.task_id for t in dag.tasks}
        expected = {"parse_pdf", "extract_facts", "validate_facts", "index_chunks", "calculate_kpis"}
        assert expected == task_ids

    def test_task_count_is_five(self):
        dag = _import_dag()
        assert len(dag.tasks) == 5


class TestDagTopology:
    """
    Verify the task dependency graph.

    Expected topology:
        parse_pdf ──► extract_facts ──► validate_facts ──► calculate_kpis
                  └──► index_chunks
    """

    def _downstream_ids(self, dag, task_id: str) -> set:
        task = dag.get_task(task_id)
        return {t.task_id for t in task.downstream_list}

    def _upstream_ids(self, dag, task_id: str) -> set:
        task = dag.get_task(task_id)
        return {t.task_id for t in task.upstream_list}

    def test_parse_pdf_has_two_downstream_tasks(self):
        dag = _import_dag()
        assert self._downstream_ids(dag, "parse_pdf") == {"extract_facts", "index_chunks"}

    def test_extract_facts_is_upstream_of_validate(self):
        dag = _import_dag()
        assert "extract_facts" in self._upstream_ids(dag, "validate_facts")

    def test_validate_facts_is_upstream_of_calculate_kpis(self):
        dag = _import_dag()
        assert "validate_facts" in self._upstream_ids(dag, "calculate_kpis")

    def test_index_chunks_has_no_downstream(self):
        dag = _import_dag()
        assert self._downstream_ids(dag, "index_chunks") == set()

    def test_calculate_kpis_has_no_downstream(self):
        dag = _import_dag()
        assert self._downstream_ids(dag, "calculate_kpis") == set()

    def test_parse_pdf_has_no_upstream(self):
        dag = _import_dag()
        assert self._upstream_ids(dag, "parse_pdf") == set()

    def test_no_cycle_in_dag(self):
        """DAG must be acyclic — Airflow enforces this, but we verify explicitly."""
        dag = _import_dag()
        # Topological sort raises CycleError if a cycle exists
        from airflow.utils.dag_cycle_tester import check_cycle
        try:
            check_cycle(dag)
        except Exception as e:
            pytest.fail(f"DAG has a cycle: {e}")


class TestDagRetryConfig:
    def test_retries_set_to_one(self):
        dag = _import_dag()
        for task in dag.tasks:
            assert task.retries == 1, f"Task {task.task_id} has {task.retries} retries, expected 1"

    def test_email_on_failure_disabled(self):
        dag = _import_dag()
        for task in dag.tasks:
            assert task.email_on_failure is False
