FROM python:3.8.8

COPY setup_environment.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db_configure.yml .
COPY tables.py .
COPY insert_api_to_table.py .
COPY instructions1.json . 
COPY instructions2.json . 
COPY run.py .

CMD ["python", "./run.py", "--host=0.0.0.0"]