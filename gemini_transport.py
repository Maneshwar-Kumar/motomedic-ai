"""Bounded Google SSE transport; request data and credentials never enter telemetry."""
import json
import shutil
import subprocess
import threading
import time

TRANSPORT_VERSION = "gemini-curl-sse-v1"
TIMING_FIELDS = ("time_namelookup", "time_connect", "time_appconnect", "time_pretransfer",
                 "time_starttransfer", "time_total", "http_code", "http_version", "num_redirects")

class TransportFailure(RuntimeError):
    def __init__(self, reason, telemetry):
        super().__init__(reason)
        self.telemetry = telemetry

def stream_request(model, key, payload, timeout_seconds):
    curl = shutil.which("curl.exe") or shutil.which("curl")
    trace = {"transport_version": TRANSPORT_VERSION, "requested_model": model,
             "first_byte_seconds": None, "first_visible_token_seconds": None,
             "completion_seconds": None, "retry_count": 0, "http_status": None,
             "usage_reported": False, "raw_content_logged": False}
    if not curl:
        raise TransportFailure("PROVIDER_TRANSPORT_UNAVAILABLE", trace)
    config = "\n".join([
        "url = " + json.dumps("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":streamGenerateContent?alt=sse"),
        "header = " + json.dumps("x-goog-api-key: " + key),
        'header = "Content-Type: application/json"',
        "data = " + json.dumps(json.dumps(payload, ensure_ascii=False, allow_nan=False)), ""])
    process, reader = None, None
    started = time.monotonic()
    try:
        process = subprocess.Popen([curl, "--silent", "--show-error", "--no-buffer",
            "--max-time", str(timeout_seconds), "--connect-timeout", str(min(10, timeout_seconds)),
            "--retry", "0", "--write-out", "%{stderr}MM_METRICS %{json}\n", "--config", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr_parts = []
        reader = threading.Thread(target=lambda: stderr_parts.append(process.stderr.read(131072)), daemon=True)
        reader.start()
        process.stdin.write(config.encode("utf-8"))
        process.stdin.close()
        chunks, total_bytes = [], 0
        while True:
            line = process.stdout.readline(131073)
            if not line:
                break
            total_bytes += len(line)
            if total_bytes > 131072:
                raise TransportFailure("PROVIDER_OUTPUT_BOUND", trace)
            if line.startswith(b"data: "):
                chunk = json.loads(line[6:])
                if not isinstance(chunk, dict):
                    raise TransportFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
                chunks.append(chunk)
                if trace["first_visible_token_seconds"] is None and any(
                    p.get("text") and not p.get("thought")
                    for c in chunk.get("candidates", []) for p in c.get("content", {}).get("parts", [])):
                    trace["first_visible_token_seconds"] = round(time.monotonic() - started, 6)
        code = process.wait(timeout=5)
        reader.join(timeout=5)
        metrics = {}
        for line in b"".join(stderr_parts).decode(errors="replace").splitlines():
            if line.startswith("MM_METRICS "):
                metrics = json.loads(line[len("MM_METRICS "):])
        trace["curl"] = {k: metrics[k] for k in TIMING_FIELDS if k in metrics}
        trace["http_status"] = metrics.get("http_code") or None
        trace["first_byte_seconds"] = metrics.get("time_starttransfer") or None
        trace["completion_seconds"] = metrics.get("time_total")
        trace["wall_seconds"] = round(time.monotonic() - started, 6)
        trace["curl_exit_code"] = code
        if code == 28:
            raise TransportFailure("PROVIDER_TIMEOUT", trace)
        if code != 0:
            raise TransportFailure("PROVIDER_CONNECTION_FAILED", trace)
        if metrics.get("num_redirects", 0) or 300 <= (trace["http_status"] or 0) < 400:
            raise TransportFailure("PROVIDER_REDIRECT_REJECTED", trace)
        status = trace["http_status"]
        if status == 429:
            raise TransportFailure("PROVIDER_QUOTA_EXHAUSTED", trace)
        if status and status >= 500:
            raise TransportFailure("PROVIDER_SERVICE_ERROR", trace)
        if status in (401, 403):
            raise TransportFailure("PROVIDER_ACCESS_ERROR", trace)
        if status != 200:
            raise TransportFailure("PROVIDER_REQUEST_REJECTED", trace)
        return chunks, trace
    except TransportFailure:
        raise
    except Exception:
        trace["wall_seconds"] = round(time.monotonic() - started, 6)
        raise TransportFailure("PROVIDER_REQUEST_FAILED", trace) from None
    finally:
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()
            if reader:
                reader.join(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
