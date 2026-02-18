#!/usr/bin/env python3
"""
Basic Streaming HTTP MCP Test Server

Implements the Model Context Protocol (MCP) using streamable HTTP transport.
Echoes back whatever is sent to it.

Usage:
    python mcp_test_server.py [--port PORT] [--host HOST]
"""

import argparse
import json
import uuid
import logging
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store active sessions
sessions: set[str] = set()


class MCPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP streamable HTTP transport."""
    
    protocol_version = 'HTTP/1.1'
    
    def log_message(self, format: str, *args) -> None:
        """Override to use our logger."""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def _send_response(
        self, 
        status: int, 
        content_type: str, 
        body: bytes,
        session_id: Optional[str] = None
    ) -> None:
        """Send HTTP response with optional session ID."""
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(body))
        if session_id:
            self.send_header('Mcp-Session-Id', session_id)
        # Allow CORS for testing
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Mcp-Session-Id')
        self.end_headers()
        self.wfile.write(body)
    
    def _accepts_streaming(self) -> bool:
        """Check if client accepts application/json-seq streaming format."""
        accept = self.headers.get('Accept', '')
        return 'application/json-seq' in accept
    
    def _send_jsonrpc_response(
        self, 
        result: dict, 
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        stream: Optional[bool] = None
    ) -> None:
        """Send a JSON-RPC response."""
        response = {
            "jsonrpc": "2.0",
            "result": result
        }
        if request_id is not None:
            response["id"] = request_id
        
        # Auto-detect streaming preference if not specified
        if stream is None:
            stream = self._accepts_streaming()
        
        if stream:
            # Streamable HTTP uses application/json-seq (RFC 7464)
            # Each JSON object is preceded by RS (Record Separator, 0x1E) and followed by LF
            body = b'\x1e' + json.dumps(response).encode('utf-8') + b'\n'
            self._send_response(200, 'application/json-seq', body, session_id)
        else:
            body = json.dumps(response).encode('utf-8')
            self._send_response(200, 'application/json', body, session_id)
    
    def _send_jsonrpc_error(
        self, 
        code: int, 
        message: str, 
        request_id: Optional[str] = None,
        status_code: int = 400
    ) -> None:
        """Send a JSON-RPC error response."""
        error_response = {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message}
        }
        if request_id is not None:
            error_response["id"] = request_id
        
        body = json.dumps(error_response).encode('utf-8')
        self._send_response(status_code, 'application/json', body)
    
    def _parse_request_body(self) -> Optional[dict]:
        """Parse the request body as JSON."""
        content_length = self.headers.get('Content-Length')
        if not content_length:
            return None
        
        try:
            length = int(content_length)
            body = self.rfile.read(length)
            return json.loads(body.decode('utf-8'))
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse request body: {e}")
            return None
    
    def _get_session_id(self) -> Optional[str]:
        """Get session ID from request headers."""
        return self.headers.get('Mcp-Session-Id')
    
    def _create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        sessions.add(session_id)
        logger.info(f"Created session: {session_id}")
        return session_id
    
    def _validate_session(self, session_id: Optional[str]) -> bool:
        """Validate if session exists."""
        if session_id is None:
            return False
        return session_id in sessions
    
    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Mcp-Session-Id')
        self.end_headers()
    
    def do_GET(self) -> None:
        """Handle GET requests - used for health checks."""
        if self.path in ['/', '/health', '/mcp']:
            response = {"status": "ok", "transport": "streamable-http"}
            body = json.dumps(response).encode('utf-8')
            self._send_response(200, 'application/json', body)
        else:
            self._send_response(404, 'application/json', 
                json.dumps({"error": "Not found"}).encode('utf-8'))
    
    def do_DELETE(self) -> None:
        """Handle DELETE requests - used to terminate sessions."""
        session_id = self._get_session_id()
        
        if not session_id:
            self._send_jsonrpc_error(-32000, "Session ID required", status_code=400)
            return
        
        if not self._validate_session(session_id):
            self._send_jsonrpc_error(-32001, "Invalid session", status_code=404)
            return
        
        sessions.discard(session_id)
        logger.info(f"Terminated session: {session_id}")
        self._send_response(200, 'application/json', json.dumps({"status": "ok"}).encode('utf-8'))
    
    def do_POST(self) -> None:
        """Handle POST requests - main MCP message endpoint."""
        session_id = self._get_session_id()
        
        # Parse request body
        request_data = self._parse_request_body()
        if request_data is None:
            self._send_jsonrpc_error(-32700, "Parse error", status_code=400)
            return
        
        # Validate JSON-RPC structure
        if not isinstance(request_data, dict) or request_data.get("jsonrpc") != "2.0":
            self._send_jsonrpc_error(-32600, "Invalid Request", status_code=400)
            return
        
        method = request_data.get("method")
        request_id = request_data.get("id")
        params = request_data.get("params", {})
        
        logger.info(f"Received method '{method}' from session {session_id or 'new'}")
        
        # Handle initialize method - create new session
        if method == "initialize":
            new_session_id = self._create_session()
            result = {
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
            }
            self._send_jsonrpc_response(result, request_id, new_session_id)
            return
        
        # For all other methods, validate session
        if not self._validate_session(session_id):
            self._send_jsonrpc_error(-32001, "Invalid or missing session", status_code=404)
            return
        
        # Handle methods - echo back whatever was sent
        if method == "tools/list":
            # Return list of available tools
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo back whatever is sent to it",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "Message to echo"
                                }
                            }
                        }
                    }
                ]
            }
            self._send_jsonrpc_response(result, request_id, session_id)
            return
        
        elif method == "tools/call":
            # Echo back the tool call with result
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {json.dumps(params, indent=2)}"
                    }
                ],
                "isError": False
            }
            self._send_jsonrpc_response(result, request_id, session_id)
        
        elif method == "resources/read":
            # Echo back resource request
            result = {
                "contents": [
                    {
                        "uri": params.get("uri", "unknown"),
                        "mimeType": "text/plain",
                        "text": f"Echo resource: {json.dumps(params, indent=2)}"
                    }
                ]
            }
            self._send_jsonrpc_response(result, request_id, session_id)
        
        elif method == "ping":
            # Simple ping/pong
            result = {}
            self._send_jsonrpc_response(result, request_id, session_id)
        
        else:
            # Default echo for any other method
            result = {
                "echo": True,
                "method": method,
                "params": params,
                "message": f"Echo from MCP test server: received {method}"
            }
            self._send_jsonrpc_response(result, request_id, session_id)


class ThreadedHTTPServer(HTTPServer):
    """Threaded HTTP server to handle multiple connections."""
    allow_reuse_address = True
    allow_reuse_port = True

    def finish_request(self, request, client_address):
        """Override to handle exceptions in request handling."""
        try:
            self.RequestHandlerClass(request, client_address, self)
        except (ConnectionResetError, BrokenPipeError):
            # Client closed connection - common with health checks, ignore
            pass
        except Exception as e:
            logger.error(f"Error handling request: {e}")


def main():
    parser = argparse.ArgumentParser(description="MCP Streaming HTTP Test Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3001, help="Port to listen on (default: 3001)")
    args = parser.parse_args()
    
    server = ThreadedHTTPServer((args.host, args.port), MCPHandler)
    
    logger.info(f"MCP Streaming HTTP Test Server starting on http://{args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        server.shutdown()
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
