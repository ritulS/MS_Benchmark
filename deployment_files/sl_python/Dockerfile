FROM python:3.11-slim

WORKDIR /app

COPY sl_requirements.txt .

RUN pip install -r sl_requirements.txt

COPY . .

CMD ["python", "sl_test.py"]