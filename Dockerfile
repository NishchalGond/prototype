FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2, lxml, xlrd
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project source
COPY . .

# Make sure engine + backend are importable
ENV PYTHONPATH=/app

# Use sh -c so $PORT is properly expanded by the shell at runtime
CMD ["sh", "-c", "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"]
