# MCP Streaming HTTP Test Server

A basic [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server using the **streamable HTTP transport**. This server simply echoes back whatever is sent to it, making it useful for testing MCP clients.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Docker Compose (Recommended)](#docker-compose-recommended)
  - [Docker](#docker)
  - [Python](#python)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Example Usage](#example-usage)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Protocol Compliance](#protocol-compliance)
- [License](#license)

## Features

| Feature | Description |
|---------|-------------|
| **Streamable HTTP** | Supports both `application/json` and `application/json-seq` (RFC 7464) |
| **Auto-detect Format** | Returns streaming format only when client requests it via `Accept` header |
| **Session Management** | Maintains sessions via `Mcp-Session-Id` header |
| **Echo Functionality** | Returns exactly what you send to it |
| **JSON-RPC 2.0** | Compliant with MCP protocol specification |
| **Zero Dependencies** | Uses only Python standard library |
| **Docker Ready** | Includes Dockerfile and docker-compose.yml |

## Quick Start

### Docker Compose (Recommended)

```bash
# Clone or download the project
git clone <repo-url>
cd mcp-test-server

# Start the server
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop the server
docker-compose down
```

Server will be available at `http://localhost:3001`.

### Docker

```bash
# Build image
docker build -t mcp-test-server .

# Run container
docker run -d \
  --name mcp-test-server \
  -p 3001:3001 \
  --restart unless-stopped \
  mcp-test-server

# Check logs
docker logs -f mcp-test-server

# Stop and remove
docker stop mcp-test-server && docker rm mcp-test-server
```

### Python

Requires Python 3.8+

```bash
# Start server
python mcp_test_server.py

# With custom options
python mcp_test_server.py --host 0.0.0.0 --port 8080

# Test with client
python test_client.py
```

## Project Structure

```
mcp-test-server/
├── mcp_test_server.py    # Main server implementation
├── test_client.py        # Test client for verification
├── requirements.txt      # Python dependencies (empty - stdlib only)
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore        # Docker build exclusions
└── README.md            # This file
```

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/` or `/mcp` | Main MCP message endpoint |
| `GET` | `/` or `/health` | Health check |
| `DELETE` | `/` | Terminate session |
| `OPTIONS` | `/` | CORS preflight |

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | Must be `application/json` |
| `Mcp-Session-Id` | After init | Session ID from `initialize` response |
| `Accept` | No | `application/json` (default) or `application/json-seq` |

### Response Formats

**Standard Response** (`application/json` - default):
```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": 1
}
```

**Streaming Response** (`application/json-seq`):
When client sends `Accept: application/json-seq`, responses use RFC 7464 JSON Text Sequences:
```
<RS>{"jsonrpc":"2.0","result":{...},"id":1}<LF>
```
(`<RS>` = Record Separator `\x1E`, `<LF>` = Line Feed `\n`)

### Supported Methods

| Method | Description |
|--------|-------------|
| `initialize` | Create new session, returns server capabilities |
| `ping` | Simple health check |
| `tools/list` | List available tools |
| `tools/call` | Echo tool calls |
| `resources/read` | Echo resource requests |
| `*` | Any other method echoes back |

## Example Usage

### 1. Initialize Session

```bash
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {}
    },
    "id": 1
  }'
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "logging": {},
      "tools": {},
      "resources": {}
    },
    "serverInfo": {
      "name": "mcp-test-server",
      "version": "1.0.0"
    }
  },
  "id": 1
}
```

> ⚠️ Save the `Mcp-Session-Id` header from the response!

### 2. List Tools

```bash
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'
```

### 3. Call a Tool

```bash
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "my-tool",
      "arguments": {"key": "value"}
    },
    "id": 3
  }'
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Echo: {\n  \"name\": \"my-tool\",\n  \"arguments\": {\n    \"key\": \"value\"\n  }\n}"
      }
    ],
    "isError": false
  },
  "id": 3
}
```

### 4. Streaming Format

```bash
curl -X POST http://127.0.0.1:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: YOUR_SESSION_ID" \
  -H "Accept: application/json-seq" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "test"},
    "id": 4
  }'
```

### 5. Terminate Session

```bash
curl -X DELETE http://127.0.0.1:3001/mcp \
  -H "Mcp-Session-Id: YOUR_SESSION_ID"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONUNBUFFERED` | Disable Python output buffering | `1` |

### Custom Port

**Docker Compose:**
```yaml
services:
  mcp-test-server:
    ports:
      - "8080:3001"  # host:container
```

**Docker:**
```bash
docker run -p 8080:3001 mcp-test-server
```

**Python:**
```bash
python mcp_test_server.py --port 8080
```

### Health Check

The Docker container includes a health check that pings the server every 30 seconds:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' mcp-test-server
```

## Troubleshooting

### "Invalid or missing session" error

Make sure to:
1. Call `initialize` first to get a session ID
2. Include `Mcp-Session-Id` header in subsequent requests

### JSON parse error with `\x1e` character

The server returns streaming format (`application/json-seq`) when the client sends `Accept: application/json-seq`. If you're getting parse errors:

- **Don't** send `Accept: application/json-seq` if your client doesn't support it
- Or handle the RS character (`\x1e`) before parsing JSON

### Port already in use

```bash
# Find process using port 3001
lsof -i :3001

# Or use a different port
python mcp_test_server.py --port 3002
```

### Docker container won't start

```bash
# Check logs
docker-compose logs

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

## Protocol Compliance

This server implements the [MCP Streamable HTTP Transport](https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/transports/#streamable-http) specification:

| Feature | Status |
|---------|--------|
| HTTP POST for messages | ✅ |
| Session management via `Mcp-Session-Id` | ✅ |
| Streaming `application/json-seq` | ✅ (opt-in via `Accept` header) |
| Standard JSON responses | ✅ (default) |
| Session termination via DELETE | ✅ |
| JSON-RPC 2.0 format | ✅ |
| CORS support | ✅ |

## License

MIT
