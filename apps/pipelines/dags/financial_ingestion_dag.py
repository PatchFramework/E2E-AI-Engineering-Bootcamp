import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging

# Add tasks and dags directories to sys.path so that pipeline tasks
# and the mounted api package (at /opt/airflow/dags/api) are importable.
sys.path.insert(0, '/opt/airflow/dags')
sys.path.insert(0, '/opt/airflow/tasks')

logger = logging.getLogger(__name__)
logger.info(f"Starting financial financial_ingestion_dag at {datetime.utcnow()}")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}


def parse_pdf_callable(**context):
    """
    Airflow task wrapper for parsing filing PDFs.
    """
    dag_run = context['dag_run']
    conf = dag_run.conf or {}
    
    document_id = conf.get('document_id')
    company_id = conf.get('company_id')
    s3_path = conf.get('s3_path')
    
    if not all([document_id, company_id, s3_path]):
        raise ValueError(f"Missing required execution parameters in dag run config: {conf}")
    
    logger.info(f"Starting parse_pdf_callable for document_id {document_id}, company_id {company_id}, s3_path {s3_path}")

    from parsing import parse_pdf
    return parse_pdf(document_id, company_id, s3_path)


def extract_facts_callable(**context):
    """
    Airflow task wrapper for structured concept extraction.
    """
    ti = context['ti']
    parsed_data = ti.xcom_pull(task_ids='parse_pdf')
    
    logger.info(f"Starting extract_facts_callable for document_id {parsed_data.get('document_id')}, company_id {parsed_data.get('company_id')}, s3_path {parsed_data.get('s3_path')}")
    
    # pyrefly: ignore [missing-import]
    from extraction import extract_facts
    return extract_facts(parsed_data)


def validate_facts_callable(**context):
    """
    Airflow task wrapper for running accounting and reconciliation validation checks.
    """
    ti = context['ti']
    extraction_result = ti.xcom_pull(task_ids='extract_facts')

    logger.info(f"Starting validate_facts_callable for document_id {extraction_result.get('document_id')}, company_id {extraction_result.get('company_id')}, s3_path {extraction_result.get('s3_path')}")
    
    from validation import validate_facts
    return validate_facts(extraction_result)


def index_chunks_callable(**context):
    """
    Airflow task wrapper for pgvector indexing and chunking.
    """
    ti = context['ti']
    parsed_data = ti.xcom_pull(task_ids='parse_pdf')
    
    logger.info(f"Starting index_chunks_callable for document_id {parsed_data.get('document_id')}, company_id {parsed_data.get('company_id')}, s3_path {parsed_data.get('s3_path')}")
    
    from indexing import index_document_chunks
    return index_document_chunks(parsed_data)


def calculate_kpis_callable(**context):
    """
    Airflow task wrapper for derived KPI metric calculations.
    """
    ti = context['ti']
    extraction_result = ti.xcom_pull(task_ids='extract_facts')
    
    company_id = extraction_result['company_id']
    year = extraction_result['fiscal_year']
    period = extraction_result['fiscal_period']
    
    logger.info(f"Starting calculate_kpis_callable for document_id {extraction_result.get('document_id')}, company_id {extraction_result.get('company_id')}, s3_path {extraction_result.get('s3_path')}")

    # Import shared API service for synchronous metrics recalculation
    from api.services.metric_calculation import MetricCalculationService
    from api.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        MetricCalculationService.recalculate_metrics_for_period(
            db,
            company_id=company_id,
            year=year,
            period=period
        )
    finally:
        db.close()
        
    return {"status": "success"}


with DAG(
    'financial_ingestion_dag',
    default_args=default_args,
    description='AI-Assisted Credit Underwriting Data Ingestion Pipeline',
    schedule_interval=None,
    catchup=False,
) as dag:

    parse_task = PythonOperator(
        task_id='parse_pdf',
        python_callable=parse_pdf_callable,
    )

    extract_task = PythonOperator(
        task_id='extract_facts',
        python_callable=extract_facts_callable,
    )

    validate_task = PythonOperator(
        task_id='validate_facts',
        python_callable=validate_facts_callable,
    )

    index_task = PythonOperator(
        task_id='index_chunks',
        python_callable=index_chunks_callable,
    )

    calculate_task = PythonOperator(
        task_id='calculate_kpis',
        python_callable=calculate_kpis_callable,
    )

    # DAG flow: 
    # 1. Parse PDF
    # 2. Extract facts and Index chunks in parallel
    # 3. Validate extracted facts
    # 4. Recalculatederived metrics/KPIs
    parse_task >> extract_task >> validate_task >> calculate_task
    parse_task >> index_task
