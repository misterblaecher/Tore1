FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1

# Render expose le port via $PORT
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
