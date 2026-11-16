#!/usr/bin/env python3
"""BioPathway MCP server (stdio transport, JSON-RPC 2.0, standard library only).

Register with Claude Code:
    claude mcp add biopathway -- python3 /path/to/biopathway-mapper/scripts/bpm_mcp.py

Implements the MCP lifecycle (initialize / notifications/initialized), tools/list
and tools/call. Tools are generated from bpm.service, the same operation table
the Explorer's HTTP API uses. Spec: https://modelcontextprotocol.io/specification
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bpm import __version__  # noqa: E402
from bpm.http import HttpClient, SourceError  # noqa: E402
from bpm.service import Service  # noqa: E402

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def tool_list(service: Service) -> list[dict]:
    tools = []
    for name, (_, desc, props, required) in sorted(service.ops().items()):
        tools.append({"name": name, "description": desc,
                      "inputSchema": {"type": "object", "properties": props, "required": required},
                      "annotations": {"readOnlyHint": True, "openWorldHint": True}})
    return tools


def handle(service: Service, msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:                       # notification: no response
        return None
    try:
        if method == "initialize":
            asked = params.get("protocolVersion")
            version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "biopathway", "version": __version__},
                      "instructions": ("Evidence-traceable molecular biology tools. Every relationship carries an "
                                       "evidence label and citations; treat graph connectivity as hypothesis, and "
                                       "follow the biopathway-mapper skill's labelling rules when answering.")}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tool_list(service)}
        elif method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            try:
                data = service.call(name, args)
                text = data["markdown"] if name == "report" else json.dumps(data, default=str)
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except (KeyError, ValueError, SourceError) as exc:
                msg_text = exc.message if isinstance(exc, SourceError) else str(exc)
                result = {"content": [{"type": "text", "text": f"Error: {msg_text}"}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    except Exception as exc:  # never die on one bad request
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    offline = os.environ.get("BPM_OFFLINE") == "1"
    service = Service(HttpClient(offline=offline), use_kegg=os.environ.get("BPM_DISABLE_KEGG") != "1")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                         "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        batch = msg if isinstance(msg, list) else [msg]
        out = [r for r in (handle(service, m) for m in batch) if r is not None]
        if out:
            sys.stdout.write(json.dumps(out if isinstance(msg, list) else out[0], default=str) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
