from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def mock_ingestion():
    print("Ingesting filing from S3/MinIO...")

def mock_parsing():
    print("Parsing PDF & layout extraction...")

def mock_extraction():
    print("Extracting financial facts via LLM...")

def mock_calculation():
    print("Calculating derived KPIs...")

with DAG(
    'financial_ingestion_dag',
    default_args=default_args,
    description='AI-Assisted Credit Underwriting Data Ingestion Pipeline',
    schedule_interval=None,
    catchup=False,
) as dag:

    ingest_task = PythonOperator(
        task_id='ingest_filing',
        python_callable=mock_ingestion,
    )

    parse_task = PythonOperator(
        task_id='parse_pdf',
        python_callable=mock_parsing,
    )

    extract_task = PythonOperator(
        task_id='extract_facts',
        python_callable=mock_extraction,
    )

    calculate_task = PythonOperator(
        task_id='calculate_kpis',
        python_callable=mock_calculation,
    )

    ingest_task >> parse_task >> extract_task >> calculate_task
