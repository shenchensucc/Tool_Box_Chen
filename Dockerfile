# Chen's Engineer Toolbox - FastAPI Backend
# For deployment to ai-builders.space

FROM python:3.11-slim

WORKDIR /app

# Install dependencies (pywin32 is Windows-only, skipped on Linux)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/

# Expose port (PORT will be set at runtime by Koyeb)
EXPOSE 8000

# Start application using PORT environment variable
# Use shell form (sh -c) to ensure environment variable expansion
CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
