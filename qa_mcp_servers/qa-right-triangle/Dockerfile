FROM python:3.13-slim

WORKDIR /app

# Copy server code
COPY server.py .

# No additional dependencies needed for basic server
# If you add dependencies later, create requirements.txt and:
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Run MCP server with stdio transport
CMD ["python3", "server.py"]
