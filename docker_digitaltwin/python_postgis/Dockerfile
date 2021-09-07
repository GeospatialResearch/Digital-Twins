FROM python:3.8.8

COPY setup_environment.py .
COPY requirements.txt .
COPY db_configure.yml .
COPY api_values.py .
COPY tables.py .
COPY insert_apis_to_db.py .
COPY instructions.json . 
COPY . . 

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "./insert_apis_to_db.py", "--host=0.0.0.0"]