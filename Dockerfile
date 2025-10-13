# ============================
# Python API with GEHistoricalImagery via gehinix.sh
# ============================
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# System deps (GDAL + build tools + .NET SDK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    wget \
    unzip \
    curl \
    libgdal-dev \
    gdal-bin \
    ca-certificates \
    git \
 && rm -rf /var/lib/apt/lists/*

# Download and setup gehinix.sh (official build script)
RUN wget https://raw.githubusercontent.com/Mbucari/GEHistoricalImagery/refs/heads/master/gehinix.sh \
 && chmod +x gehinix.sh \
 && ./gehinix.sh --help || echo "gehinix.sh downloaded"

# Create wrapper script for GEHistoricalImagery
RUN echo '#!/bin/bash\n/app/gehinix.sh "$@"' > /usr/local/bin/GEHistoricalImagery \
 && chmod +x /usr/local/bin/GEHistoricalImagery

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p storage/temp storage/logs storage/cache

# Expose API port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8006/api/health || exit 1

# Run the application
CMD ["python", "run.py"]