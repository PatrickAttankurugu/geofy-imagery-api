# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    unzip \
    curl \
    libgdal-dev \
    gdal-bin \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install .NET Runtime for GEHistoricalImagery
RUN wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh \
    && chmod +x dotnet-install.sh \
    && ./dotnet-install.sh --channel 8.0 --install-dir /usr/share/dotnet \
    && rm dotnet-install.sh

# Add .NET to PATH
ENV DOTNET_ROOT=/usr/share/dotnet
ENV PATH=$PATH:/usr/share/dotnet

# Download and install GEHistoricalImagery
RUN wget https://github.com/Mbucari/GEHistoricalImagery/releases/latest/download/GEHistoricalImagery-linux-x64.zip \
    && unzip GEHistoricalImagery-linux-x64.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/GEHistoricalImagery \
    && rm GEHistoricalImagery-linux-x64.zip

# Verify GEHistoricalImagery installation
RUN /usr/local/bin/GEHistoricalImagery --version || echo "GEHistoricalImagery installed"

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p storage/temp storage/logs storage/cache

# Expose port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8006/api/health || exit 1

# Run the application
CMD ["python", "run.py"]