# Chen's Engineer Toolbox - Full Stack (Frontend + Backend)
# For deployment to ai-builders.space
# Serves Streamlit UI on PORT, FastAPI backend on 8000 (internal)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies (pywin32 is Windows-only, skipped on Linux)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Streamlit talks to backend via localhost (backend on 8001 to avoid PORT conflict)
ENV BACKEND_URL=http://127.0.0.1:8001

# Expose port (PORT set at runtime by Koyeb)
EXPOSE 8000

# Run backend on 8001 (internal) + Streamlit on PORT (exposed to internet)
# Platform routes external traffic to PORT - visitors see Streamlit UI
CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port 8001 & streamlit run frontend/Home.py --server.port ${PORT:-8000} --server.address 0.0.0.0 --server.headless true"
