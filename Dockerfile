FROM python:3.12-slim

# Install system dependencies required for building some python packages
# and for healthchecks (curl)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set default command (can be overridden by Render)
# We set it to run the API by default.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
