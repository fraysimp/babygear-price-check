FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY wsgi.py .
COPY data/ data/

# Seed the database if it doesn't exist
RUN python -c "from src.babygear_web.seed_data import seed; seed()"

ENV PORT=10000
ENV DB_PATH=/app/data/babygear.db

EXPOSE 10000

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:10000", "--workers", "2", "--timeout", "120"]
