FROM golang:latest

WORKDIR /app

# COPY sl_requirements.txt .

# RUN pip install -r sl_requirements.txt

COPY . .

RUN ["go", "build"]

CMD ["./sltest"]