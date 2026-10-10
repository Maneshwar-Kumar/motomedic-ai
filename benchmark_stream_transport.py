"""Experimental SSE callback transport; production transport is unchanged."""
import json
import shutil
import subprocess
import threading
import time

from gemini_transport import _curl_config, TransportFailure, TIMING_FIELDS


def stream_request(model, key, payload, timeout_seconds, on_chunk):
    trace = {"transport_version": "benchmark-curl-sse-callback-v1",
             "requested_model": model, "first_visible_token_seconds": None,
             "completion_seconds": None, "http_status": None, "retry_count": 0,
             "raw_content_logged": False}
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise TransportFailure("PROVIDER_TRANSPORT_UNAVAILABLE", trace)
    started = time.monotonic()
    process = None
    reader = None
    try:
        process = subprocess.Popen([curl, "--silent", "--show-error", "--no-buffer",
            "--max-time", str(timeout_seconds), "--connect-timeout", str(min(10, timeout_seconds)),
            "--retry", "0", "--write-out", "%{stderr}MM_METRICS %{json}\n", "--config", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr_parts = []
        reader = threading.Thread(target=lambda: stderr_parts.append(process.stderr.read(131072)), daemon=True)
        reader.start()
        process.stdin.write(_curl_config(model, key, payload).encode("utf-8"))
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
                    p.get("text") and not p.get("thought") for c in chunk.get("candidates", [])
                    for p in c.get("content", {}).get("parts", [])):
                    trace["first_visible_token_seconds"] = time.monotonic() - started
                on_chunk(chunk)
        code = process.wait(timeout=5)
        reader.join(timeout=5)
        metrics = {}
        for line in b"".join(stderr_parts).decode(errors="replace").splitlines():
            if line.startswith("MM_METRICS "):
                metrics = json.loads(line[len("MM_METRICS "):])
        trace.update(http_status=metrics.get("http_code"), completion_seconds=metrics.get("time_total"),
                     first_byte_seconds=metrics.get("time_starttransfer"),
                     wall_seconds=time.monotonic() - started, curl_exit_code=code,
                     curl={k: metrics[k] for k in TIMING_FIELDS if k in metrics})
        status = trace["http_status"]
        reason = ("PROVIDER_TIMEOUT" if code == 28 else "PROVIDER_CONNECTION_FAILED" if code else
                  "PROVIDER_REDIRECT_REJECTED" if metrics.get("num_redirects", 0) or 300 <= (status or 0) < 400 else
                  "PROVIDER_QUOTA_EXHAUSTED" if status == 429 else
                  "PROVIDER_SERVICE_ERROR" if status and status >= 500 else
                  "PROVIDER_ACCESS_ERROR" if status in (401, 403) else
                  "PROVIDER_REQUEST_REJECTED" if status != 200 else None)
        if reason:
            raise TransportFailure(reason, trace)
        return chunks, trace
    except TransportFailure:
        raise
    except Exception:
        trace["wall_seconds"] = time.monotonic() - started
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
