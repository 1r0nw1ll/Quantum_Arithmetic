FROM python:3.13-slim

WORKDIR /app

# Copy server code
COPY server.py .

# No additional dependencies needed for basic server
# If you add dependencies later, create requirements.txt and:
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Expose port 7000 for MCP communication
EXPOSE 7000

# Run MCP server
CMD ["python3", "server.py"]
