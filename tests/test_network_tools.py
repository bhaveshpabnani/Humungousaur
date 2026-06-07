from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools import default_tools
from humungousaur.tools.network_tools import DnsLookupTool, HttpEndpointCheckTool, TcpConnectivityProbeTool


class _OkHandler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        self.send_response(204)
        self.send_header("X-Smoke", "network")
        self.end_headers()

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Humungousaur network smoke")

    def log_message(self, format: str, *args) -> None:
        return


class NetworkToolTests(unittest.TestCase):
    def test_dns_lookup_localhost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = DnsLookupTool().execute({"hostname": "localhost", "record_types": ["A", "AAAA"], "reason": "Verify DNS diagnostic."}, config)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["resolved"])
        self.assertIn(result.output["addresses"][0]["record_type"], {"A", "AAAA"})
        self.assertTrue(result.output["safety_note"].startswith("Diagnostic only"))

    def test_http_endpoint_check_local_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            server = HTTPServer(("127.0.0.1", 0), _OkHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                result = HttpEndpointCheckTool().execute(
                    {"url": f"http://127.0.0.1:{port}/health", "method": "GET", "timeout_seconds": 2, "reason": "Verify HTTP diagnostic."},
                    config,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(result.output["reachable"])
        self.assertEqual(result.output["status_code"], 200)
        self.assertIn("Humungousaur network smoke", result.output["body_preview"])

    def test_tcp_connectivity_probe_open_and_closed_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            accepted: list[socket.socket] = []

            def accept_once() -> None:
                connection, _address = server.accept()
                accepted.append(connection)

            thread = threading.Thread(target=accept_once, daemon=True)
            thread.start()
            try:
                open_result = TcpConnectivityProbeTool().execute(
                    {"host": "127.0.0.1", "port": port, "timeout_seconds": 2, "reason": "Verify TCP diagnostic."},
                    config,
                )
            finally:
                for connection in accepted:
                    connection.close()
                server.close()
                thread.join(timeout=5)

            closed_result = TcpConnectivityProbeTool().execute(
                {"host": "127.0.0.1", "port": port, "timeout_seconds": 0.2, "reason": "Verify closed TCP diagnostic."},
                config,
            )

        self.assertEqual(open_result.status, ActionStatus.SUCCEEDED)
        self.assertTrue(open_result.output["reachable"])
        self.assertEqual(closed_result.status, ActionStatus.SUCCEEDED)
        self.assertFalse(closed_result.output["reachable"])

    def test_network_tools_are_in_global_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
            tools = default_tools(config)

        self.assertIn("dns_lookup", tools)
        self.assertIn("http_endpoint_check", tools)
        self.assertIn("tcp_connectivity_probe", tools)
        self.assertEqual(tools["dns_lookup"].capability_group, "network")


if __name__ == "__main__":
    unittest.main()
