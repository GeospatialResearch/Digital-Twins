FROM python:3.8.8

WORKDIR app/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY setup_environment.py .
COPY db_configure.yml .
COPY api_values.py .
COPY tables.py .
COPY insert_apis_to_db.py .
COPY instructions.json . 

CMD ["python", "./insert_apis_to_db.py", "--host=0.0.0.0"]