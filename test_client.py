#!/usr/bin/env python3
"""
Test client for the MCP Streaming HTTP Test Server.

Usage:
    python test_client.py [--url URL]
"""

import argparse
import json
import http.client


def send_request(host: str, port: int, method: str, params: dict, session_id: str = None):
    """Send a JSON-RPC request to the MCP server."""
    request_id = 1
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    
    body = json.dumps(payload)
    
    conn = http.client.HTTPConnection(host, port)
    headers = {
        "Content-Type": "application/json",
        "Content-Length": len(body)
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    
    print(f"\n>>> Sending request:")
    print(f"    Method: {method}")
    print(f"    Session: {session_id or 'new session'}")
    print(f"    Body: {body}")
    
    conn.request("POST", "/mcp", body, headers)
    response = conn.getresponse()
    
    session_id = response.getheader('Mcp-Session-Id')
    data = response.read()
    
    print(f"\n<<< Received response:")
    print(f"    Status: {response.status}")
    print(f"    Session: {session_id}")
    print(f"    Content-Type: {response.getheader('Content-Type')}")
    
    # Handle json-seq responses (streaming)
    content_type = response.getheader('Content-Type', '')
    if 'json-seq' in content_type:
        # Parse JSON text sequence (RS + JSON + LF)
        text = data.decode('utf-8')
        # Split by RS character (0x1E)
        parts = text.split('\x1e')
        for part in parts:
            part = part.strip()
            if part:
                try:
                    parsed = json.loads(part)
                    print(f"    Body: {json.dumps(parsed, indent=4)}")
                except json.JSONDecodeError:
                    print(f"    Raw: {part}")
    else:
        try:
            parsed = json.loads(data)
            print(f"    Body: {json.dumps(parsed, indent=4)}")
        except json.JSONDecodeError:
            print(f"    Raw: {data.decode('utf-8')}")
    
    conn.close()
    return session_id


def main():
    parser = argparse.ArgumentParser(description="MCP Test Client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3001, help="Server port (default: 3001)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("MCP Streaming HTTP Test Client")
    print("=" * 60)
    
    # Step 1: Initialize session
    print("\n" + "=" * 60)
    print("STEP 1: Initialize Session")
    print("=" * 60)
    
    session_id = send_request(
        args.host, args.port,
        "initialize",
        {"protocolVersion": "2024-11-05", "capabilities": {}}
    )
    
    if not session_id:
        print("ERROR: No session ID received!")
        return
    
    # Step 2: Ping
    print("\n" + "=" * 60)
    print("STEP 2: Ping")
    print("=" * 60)
    
    send_request(args.host, args.port, "ping", {}, session_id)
    
    # Step 3: List tools
    print("\n" + "=" * 60)
    print("STEP 3: List Tools")
    print("=" * 60)
    
    send_request(args.host, args.port, "tools/list", {}, session_id)
    
    # Step 4: Call a tool (echo test)
    print("\n" + "=" * 60)
    print("STEP 3: Tool Call (Echo Test)")
    print("=" * 60)
    
    send_request(
        args.host, args.port,
        "tools/call",
        {"name": "test-tool", "arguments": {"hello": "world", "number": 42}},
        session_id
    )
    
    # Step 5: Read a resource (echo test)
    print("\n" + "=" * 60)
    print("STEP 5: Resource Read (Echo Test)")
    print("=" * 60)
    
    send_request(
        args.host, args.port,
        "resources/read",
        {"uri": "test://resource/path"},
        session_id
    )
    
    # Step 6: Custom method (echo test)
    print("\n" + "=" * 60)
    print("STEP 6: Custom Method (Echo Test)")
    print("=" * 60)
    
    send_request(
        args.host, args.port,
        "custom/method",
        {"data": "any data here", "nested": {"key": "value"}},
        session_id
    )
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
