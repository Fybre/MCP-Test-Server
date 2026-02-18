# MCP Streaming HTTP Test Server Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Copy server files
COPY mcp_test_server.py .
COPY requirements.txt .

# No dependencies to install, but keeping for future extensibility
RUN pip install --no-cache-dir -r requirements.txt || true

# Expose the default port
EXPOSE 3001

# Run the server
CMD ["python", "mcp_test_server.py", "--host", "0.0.0.0", "--port", "3001"]
