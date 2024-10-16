FROM python:3.11-slim  

WORKDIR /app

COPY client_requirements.txt .
RUN pip install -r client_requirements.txt

COPY . .

#RUN tail -f /dev/null