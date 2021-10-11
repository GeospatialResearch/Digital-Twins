FROM python:3.8 as base
WORKDIR app/

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY db_configure.yml .
COPY src/ src/

CMD ["python", "src/run.py"]
