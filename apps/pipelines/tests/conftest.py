"""
conftest.py — pytest configuration for pipeline integration tests.

Sets up sys.path so the api package and task modules are importable
locally without requiring a running Docker environment. External
services (OpenAI, MinIO, PostgreSQL/pgvector) are fully mocked.
"""
import sys
import os
from unittest.mock import MagicMock
import pytest

# ---------------------------------------------------------------------------
# sys.path setup — supports both local repo layout and Airflow container layout.
#
# Local layout (relative to this file):
#   apps/api/src  →  contains the `api` package
#   apps/pipelines/tasks  →  contains parsing.py, extraction.py, etc.
#
# Container layout (volume-mounted):
#   /opt/airflow/dags  →  contains the `api` sub-package (mounted as dags/api)
#   /opt/airflow/tasks  →  contains parsing.py, extraction.py, etc.
# ---------------------------------------------------------------------------
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Container paths (always add; they're no-ops if they don't exist)
CONTAINER_DAGS = "/opt/airflow/dags"
CONTAINER_TASKS = "/opt/airflow/tasks"

# Local repo paths (3 levels up from apps/pipelines/tests/)
REPO_ROOT = os.path.abspath(os.path.join(TESTS_DIR, "..", "..", ".."))
LOCAL_API_PARENT = os.path.join(REPO_ROOT, "apps", "api", "src")
LOCAL_TASKS = os.path.join(REPO_ROOT, "apps", "pipelines", "tasks")
# When running locally, also expose dags/ so `from api.xxx` resolves
LOCAL_DAGS = os.path.join(REPO_ROOT, "apps", "pipelines", "dags")

for p in [CONTAINER_TASKS, CONTAINER_DAGS, LOCAL_TASKS, LOCAL_DAGS, LOCAL_API_PARENT]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Stub out pgvector before any model imports so tests run without Postgres.
# ---------------------------------------------------------------------------
import json
from sqlalchemy.types import TypeDecorator, VARCHAR

class MockVector(TypeDecorator):
    impl = VARCHAR
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, (list, tuple)):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

pgvector_stub = MagicMock()
pgvector_stub.sqlalchemy.Vector = lambda dim: MockVector()
sys.modules.setdefault("pgvector", pgvector_stub)
sys.modules.setdefault("pgvector.sqlalchemy", pgvector_stub.sqlalchemy)

# ---------------------------------------------------------------------------
# Stub out airflow if running outside an Airflow container.
# ---------------------------------------------------------------------------
try:
    import airflow
except ImportError:
    _CURRENT_DAG = None

    class MockDAG:
        def __init__(self, dag_id, default_args=None, schedule_interval=None, catchup=False, description=None):
            self.dag_id = dag_id
            self.default_args = default_args or {}
            self.schedule_interval = schedule_interval
            self.catchup = catchup
            self.description = description
            self.tasks = []

        def __enter__(self):
            global _CURRENT_DAG
            _CURRENT_DAG = self
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            global _CURRENT_DAG
            _CURRENT_DAG = None

        def get_task(self, task_id):
            for t in self.tasks:
                if t.task_id == task_id:
                    return t
            raise KeyError(task_id)

    class MockTask:
        def __init__(self, task_id, python_callable=None, dag=None, **kwargs):
            self.task_id = task_id
            self.python_callable = python_callable
            self.retries = kwargs.get("retries", 1)
            self.email_on_failure = kwargs.get("email_on_failure", False)
            self.downstream_list = set()
            self.upstream_list = set()
            target_dag = dag or _CURRENT_DAG
            if target_dag is not None:
                target_dag.tasks.append(self)

        def __rshift__(self, other):
            if isinstance(other, (list, tuple, set)):
                for o in other:
                    self >> o
            else:
                self.downstream_list.add(other)
                other.upstream_list.add(self)
            return other

        def __lshift__(self, other):
            if isinstance(other, (list, tuple, set)):
                for o in other:
                    self << o
            else:
                self.upstream_list.add(other)
                other.downstream_list.add(self)
            return other

    airflow_mock = MagicMock()
    airflow_mock.DAG = MockDAG
    airflow_operators_mock = MagicMock()
    airflow_operators_mock.python.PythonOperator = MockTask
    airflow_utils_mock = MagicMock()
    airflow_utils_mock.dag_cycle_tester.check_cycle = lambda dag: None

    sys.modules.setdefault("airflow", airflow_mock)
    sys.modules.setdefault("airflow.operators", airflow_operators_mock)
    sys.modules.setdefault("airflow.operators.python", airflow_operators_mock.python)
    sys.modules.setdefault("airflow.utils", airflow_utils_mock)
    sys.modules.setdefault("airflow.utils.dag_cycle_tester", airflow_utils_mock.dag_cycle_tester)


# ---------------------------------------------------------------------------
# Shared sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_parsed_data():
    """
    Minimal parsed-PDF payload that mimics the output of parse_pdf().
    Contains two pages with enough text for downstream tasks.
    """
    return {
        "document_id": 1,
        "company_id": 10,
        "pages": [
            {
                "page_number": 1,
                "displayed_page_number": None,
                "section_path": "",
                "blocks": [
                    {
                        "id": "p1_b0",
                        "text": "Annual Report FY 2024",
                        "bbox": [50, 50, 500, 70],
                    }
                ],
            },
            {
                "page_number": 2,
                "displayed_page_number": "1",
                "section_path": "Item 8 > Financial Statements",
                "blocks": [
                    {
                        "id": "p2_b0",
                        "text": "Revenue for the fiscal year was $500,000,000.",
                        "bbox": [50, 100, 500, 120],
                    },
                    {
                        "id": "p2_b1",
                        "text": "Total Debt as of December 31, 2024 was $200,000,000.",
                        "bbox": [50, 130, 500, 150],
                    },
                    {
                        "id": "p2_b2",
                        "text": "EBITDA reached $120,000,000.",
                        "bbox": [50, 160, 500, 180],
                    },
                ],
            },
        ],
    }


@pytest.fixture()
def sample_extraction_result():
    """
    Minimal extraction result payload that mimics the output of extract_facts().
    """
    return {
        "document_id": 1,
        "company_id": 10,
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "fact_ids": [101, 102, 103],
    }
