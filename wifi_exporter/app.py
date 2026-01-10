import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer


def _parse_signal(output: str) -> int | None:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("signal:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(float(parts[1]))
                except ValueError:
                    return None
    return None


def _signal_to_percent(signal_dbm: int) -> int:
    normalized = 2 * (signal_dbm + 100)
    return int(max(0, min(100, normalized)))


def _read_wifi(interface: str) -> dict:
    result = subprocess.run(
        ["iw", "dev", interface, "link"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {
            "interface": interface,
            "percent": None,
            "error": result.stderr.strip() or result.stdout.strip(),
        }
    if "Not connected." in result.stdout:
        return {"interface": interface, "percent": None}
    signal = _parse_signal(result.stdout)
    if signal is None:
        return {"interface": interface, "percent": None}
    return {"interface": interface, "percent": _signal_to_percent(signal), "signal_dbm": signal}


class WifiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/wifi":
            self.send_response(404)
            self.end_headers()
            return
        interface = os.getenv("WIFI_INTERFACE", "wlan0")
        payload = _read_wifi(interface)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    host = os.getenv("WIFI_HOST", "0.0.0.0")
    port = int(os.getenv("WIFI_PORT", "9100"))
    server = HTTPServer((host, port), WifiHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
