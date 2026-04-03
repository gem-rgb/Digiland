FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . /app/

# Expose port
EXPOSE 8000

# Run gunicorn targeting localhost/0.0.0.0 for docker exposing
# (Will be accessible via the 'pinnaclce' host mapping in ALLOWED_HOSTS)
CMD ["gunicorn", "land_escrow.wsgi:application", "--bind", "0.0.0.0:8000"]
