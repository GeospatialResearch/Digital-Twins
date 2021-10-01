FROM python:3

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY setup_environment.py .
COPY ../../db_configure.yml .
COPY tables.py .
COPY insert_api_to_table.py .
COPY instructions_linz.json . 
COPY instructions_lris.json . 
COPY instructions_statsnz.json . 
COPY ../run.py .

CMD ["python", "./run.py"]
