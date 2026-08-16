import httpx
import logging
from typing import Optional, Dict, Any
from api.core.config import config

logger = logging.getLogger("api.services.airflow_service")

class AirflowService:
    @staticmethod
    def trigger_financial_ingestion(
        document_id: int,
        company_id: int,
        fiscal_year: int,
        fiscal_period: str,
        document_type: str,
        s3_path: str,
        content_hash: str
    ) -> Optional[str]:
        """
        Triggers the financial_ingestion_dag DAG run on Airflow.
        Returns the DAG run ID if successful, otherwise None.
        """
        import uuid
        generated_run_id = f"manual__{uuid.uuid4()}"
        url = f"{config.AIRFLOW_URL}/api/v1/dags/financial_ingestion_dag/dagRuns"
        payload = {
            "dag_run_id": generated_run_id,
            "conf": {
                "document_id": document_id,
                "company_id": company_id,
                "fiscal_year": fiscal_year,
                "fiscal_period": fiscal_period,
                "document_type": document_type,
                "s3_path": s3_path,
                "content_hash": content_hash
            }
        }
        
        logger.info(f"Triggering Airflow DAG financial_ingestion_dag at {url} with payload {payload}")
        try:
            with httpx.Client() as client:
                response = client.post(
                    url,
                    json=payload,
                    auth=(config.AIRFLOW_USERNAME, config.AIRFLOW_PASSWORD),
                    timeout=10.0
                )
                if response.status_code in (200, 201, 202):
                    data = response.json()
                    dag_run_id = data.get("dag_run_id") or generated_run_id
                    logger.info(f"Successfully triggered Airflow DAG, dag_run_id: {dag_run_id}")
                    return dag_run_id
                else:
                    logger.error(
                        f"Failed to trigger Airflow DAG. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return None
        except httpx.ReadTimeout:
            logger.warning(f"Read timeout while triggering Airflow DAG. Assuming it was triggered with run ID: {generated_run_id}")
            return generated_run_id
        except Exception as e:
            logger.exception(f"Exception occurred while calling Airflow API: {e}")
            return None

    @staticmethod
    def get_dag_run_status(dag_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the current state of a DAG run from the Airflow REST API.
        Returns a dict with 'state' and 'tasks', or None on error.

        Airflow DAG run states: queued | running | success | failed
        Task instance states: queued | running | success | failed | upstream_failed | skipped
        """
        url = f"{config.AIRFLOW_URL}/api/v1/dags/financial_ingestion_dag/dagRuns/{dag_run_id}"
        tasks_url = f"{config.AIRFLOW_URL}/api/v1/dags/financial_ingestion_dag/dagRuns/{dag_run_id}/taskInstances"
        try:
            with httpx.Client() as client:
                auth = (config.AIRFLOW_USERNAME, config.AIRFLOW_PASSWORD)

                run_resp = client.get(url, auth=auth, timeout=10.0)
                if run_resp.status_code != 200:
                    logger.error(f"Could not fetch DAG run status. Status: {run_resp.status_code}")
                    return None
                run_data = run_resp.json()

                tasks_resp = client.get(tasks_url, auth=auth, timeout=10.0)
                tasks = []
                if tasks_resp.status_code == 200:
                    for ti in tasks_resp.json().get("task_instances", []):
                        tasks.append({
                            "task_id": ti.get("task_id"),
                            "state": ti.get("state") or "queued",
                            "start_date": ti.get("start_date"),
                            "end_date": ti.get("end_date"),
                        })

                return {
                    "dag_run_id": dag_run_id,
                    "state": run_data.get("state"),
                    "start_date": run_data.get("start_date"),
                    "end_date": run_data.get("end_date"),
                    "tasks": tasks,
                }
        except Exception as e:
            logger.exception(f"Exception fetching DAG run status for {dag_run_id}: {e}")
            return None
