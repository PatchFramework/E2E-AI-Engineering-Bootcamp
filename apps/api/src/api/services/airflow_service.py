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
        url = f"{config.AIRFLOW_URL}/api/v1/dags/financial_ingestion_dag/dagRuns"
        payload = {
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
                if response.status_code == 201:
                    data = response.json()
                    dag_run_id = data.get("dag_run_id")
                    logger.info(f"Successfully triggered Airflow DAG, dag_run_id: {dag_run_id}")
                    return dag_run_id
                else:
                    logger.error(
                        f"Failed to trigger Airflow DAG. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return None
        except Exception as e:
            logger.exception(f"Exception occurred while calling Airflow API: {e}")
            return None
