FROM python:3.11-slim-bullseye

# Security: Create non-root user
RUN groupadd --gid 1000 tab && \
    useradd --uid 1000 --gid tab --shell /bin/bash --create-home tab

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R tab:tab /app

# Security: Switch to non-root user
USER tab

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "tab.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]