from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from pathlib import Path
import socket
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_DNS_RESULTS = 40
MAX_HTTP_BODY_BYTES = 4096
MAX_TIMEOUT_SECONDS = 10.0


class DnsLookupTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="dns_lookup",
            description="Resolve one hostname with bounded DNS diagnostics and no network setting changes.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "hostname": {"type": "string"},
                    "record_types": {"type": "array", "items": {"type": "string"}, "description": "Requested logical record types such as A, AAAA, or CNAME. Stdlib resolver returns address records only."},
                    "reason": {"type": "string"},
                },
                required=["hostname", "reason"],
            ),
            capability_group="network",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        hostname = _hostname(tool_input.get("hostname"))
        reason = str(tool_input.get("reason") or "").strip()
        if not hostname or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Hostname and reason are required.")
        record_types = _record_types(tool_input.get("record_types"))
        started = datetime.now(timezone.utc)
        addresses: list[dict[str, Any]] = []
        error = ""
        try:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            seen: set[tuple[str, str]] = set()
            for family, _socktype, _proto, canonname, sockaddr in infos:
                address = str(sockaddr[0])
                family_name = "AAAA" if family == socket.AF_INET6 else "A" if family == socket.AF_INET else str(family)
                key = (family_name, address)
                if key in seen:
                    continue
                seen.add(key)
                addresses.append(
                    {
                        "record_type": family_name,
                        "address": address,
                        "canonname": canonname,
                        "classification": _address_classification(address),
                    }
                )
                if len(addresses) >= MAX_DNS_RESULTS:
                    break
        except socket.gaierror as exc:
            error = str(exc)
        filtered = [item for item in addresses if item["record_type"] in record_types] if record_types else addresses
        output = {
            "hostname": hostname,
            "requested_record_types": record_types or ["A", "AAAA"],
            "resolved": bool(filtered),
            "addresses": filtered,
            "unfiltered_address_count": len(addresses),
            "error": error,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "safety_note": "Diagnostic only. No DNS, proxy, firewall, or network settings were changed.",
        }
        summary = f"Resolved {hostname} to {len(filtered)} address record(s)." if filtered else f"No address records resolved for {hostname}."
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, summary, output)


class HttpEndpointCheckTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="http_endpoint_check",
            description="Check one HTTP/HTTPS endpoint with bounded timeout, redirect, TLS, and response metadata. Does not mutate remote state.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["HEAD", "GET"]},
                    "timeout_seconds": {"type": "number", "minimum": 0.1, "maximum": MAX_TIMEOUT_SECONDS},
                    "follow_redirects": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                required=["url", "reason"],
            ),
            capability_group="network",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        url = str(tool_input.get("url") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not url or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "URL and reason are required.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "URL must be absolute http or https.")
        method = str(tool_input.get("method") or "HEAD").strip().upper()
        if method not in {"HEAD", "GET"}:
            method = "HEAD"
        timeout = _timeout(tool_input.get("timeout_seconds"))
        follow_redirects = bool(tool_input.get("follow_redirects", True))
        request = Request(url, method=method, headers={"User-Agent": "Humungousaur-Network-Diagnostic/1.0"})
        opener = build_opener() if follow_redirects else build_opener(_NoRedirectHandler)
        started = datetime.now(timezone.utc)
        output: dict[str, Any] = {
            "url": url,
            "method": method,
            "follow_redirects": follow_redirects,
            "timeout_seconds": timeout,
            "reachable": False,
            "status_code": None,
            "reason_phrase": "",
            "final_url": "",
            "redirected": False,
            "headers": {},
            "body_preview": "",
            "tls": _tls_summary(parsed),
            "error": "",
            "started_at": started.isoformat(),
            "safety_note": "Diagnostic only. No remote mutation or local network setting change was attempted.",
        }
        try:
            with opener.open(request, timeout=timeout) as response:
                body = response.read(MAX_HTTP_BODY_BYTES) if method == "GET" else b""
                final_url = response.geturl()
                output.update(
                    {
                        "reachable": True,
                        "status_code": int(response.status),
                        "reason_phrase": getattr(response, "reason", ""),
                        "final_url": final_url,
                        "redirected": final_url != url,
                        "headers": _safe_headers(dict(response.headers.items())),
                        "body_preview": body.decode("utf-8", errors="replace")[:MAX_HTTP_BODY_BYTES],
                    }
                )
        except HTTPError as exc:
            output.update(
                {
                    "reachable": True,
                    "status_code": int(exc.code),
                    "reason_phrase": exc.reason,
                    "final_url": exc.geturl(),
                    "redirected": exc.geturl() != url,
                    "headers": _safe_headers(dict(exc.headers.items())) if exc.headers else {},
                    "error": str(exc),
                }
            )
        except (URLError, TimeoutError, socket.timeout, ssl.SSLError, OSError) as exc:
            output["error"] = str(exc)
        output["completed_at"] = datetime.now(timezone.utc).isoformat()
        status = output["status_code"]
        summary = f"Checked {url}: HTTP {status}." if status is not None else f"Checked {url}: unreachable or no HTTP response."
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, summary, output)


class TcpConnectivityProbeTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tcp_connectivity_probe",
            description="Probe one TCP host:port with a bounded timeout. This is a single-target diagnostic, not a scanner.",
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "host": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "timeout_seconds": {"type": "number", "minimum": 0.1, "maximum": MAX_TIMEOUT_SECONDS},
                    "reason": {"type": "string"},
                },
                required=["host", "port", "reason"],
            ),
            capability_group="network",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        host = _hostname(tool_input.get("host"))
        reason = str(tool_input.get("reason") or "").strip()
        try:
            port = int(tool_input.get("port"))
        except (TypeError, ValueError):
            port = 0
        if not host or not port or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Host, port, and reason are required.")
        timeout = _timeout(tool_input.get("timeout_seconds"))
        started = datetime.now(timezone.utc)
        reachable = False
        error = ""
        peer = ""
        try:
            with socket.create_connection((host, port), timeout=timeout) as connection:
                reachable = True
                peer = f"{connection.getpeername()[0]}:{connection.getpeername()[1]}"
        except OSError as exc:
            error = str(exc)
        output = {
            "host": host,
            "port": port,
            "timeout_seconds": timeout,
            "reachable": reachable,
            "peer": peer,
            "error": error,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "safety_note": "Single host:port diagnostic only. No scan range or network setting change was attempted.",
        }
        summary = f"TCP {host}:{port} is reachable." if reachable else f"TCP {host}:{port} is not reachable."
        return ToolResult(self.name, ActionStatus.SUCCEEDED, self.risk_level, summary, output)


def default_network_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        DnsLookupTool(),
        HttpEndpointCheckTool(),
        TcpConnectivityProbeTool(),
    ]
    return {tool.name: tool for tool in tools}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _hostname(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 253 or any(char.isspace() for char in text):
        return ""
    return text.rstrip(".")


def _record_types(value: Any) -> list[str]:
    allowed = {"A", "AAAA", "CNAME"}
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        values = []
    return [str(item).strip().upper() for item in values if str(item).strip().upper() in allowed]


def _address_classification(address: str) -> dict[str, bool]:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return {"private": False, "loopback": False, "link_local": False, "multicast": False, "reserved": False}
    return {
        "private": parsed.is_private,
        "loopback": parsed.is_loopback,
        "link_local": parsed.is_link_local,
        "multicast": parsed.is_multicast,
        "reserved": parsed.is_reserved,
    }


def _timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = 3.0
    return max(0.1, min(timeout, MAX_TIMEOUT_SECONDS))


def _tls_summary(parsed_url) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if parsed_url.scheme != "https":
        return {"enabled": False}
    return {"enabled": True, "server_name": parsed_url.hostname or "", "verification": "system_default"}


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    sensitive = {"authorization", "proxy-authorization", "set-cookie", "cookie", "x-api-key"}
    for key, value in headers.items():
        if key.lower() in sensitive:
            redacted[key] = "[redacted]"
        else:
            redacted[key] = str(value)[:500]
    return redacted
