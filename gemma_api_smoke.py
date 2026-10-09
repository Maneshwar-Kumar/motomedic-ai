"""Bounded synthetic Gemini probes; credentials and response text are never logged."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import threading

MODEL = "gemma-4-31b-it"
FIELDS = ("time_namelookup", "time_connect", "time_appconnect", "time_pretransfer",
          "time_starttransfer", "time_total", "http_code", "http_version",
          "num_redirects", "num_connects", "size_upload", "size_download", "proxy_used")

def summarize(metrics, first_event, first_text, chunks, exit_code, wall):
    candidates = [c for chunk in chunks for c in chunk.get("candidates", [])]
    ready = any("READY" in p.get("text", "") for c in candidates
                for p in c.get("content", {}).get("parts", []) if not p.get("thought"))
    finish = [c["finishReason"] for c in candidates if c.get("finishReason")]
    versions = sorted({c["modelVersion"] for c in chunks if c.get("modelVersion")})
    ok = exit_code == 0 and metrics.get("http_code") == 200 and ready and "STOP" in finish and versions == [MODEL]
    usage = next((c["usageMetadata"] for c in reversed(chunks) if c.get("usageMetadata")), {})
    # Absolute curl times start at connection setup. Derived phases are client-observed.
    def delta(end, start):
        if end not in metrics or start not in metrics:
            return None
        if metrics[end] <= 0 or metrics[end] < metrics[start]:
            return None
        return round(metrics[end] - metrics[start], 4)
    return {"ok": ok, "curl_exit_code": exit_code,
            "curl": {k: metrics[k] for k in FIELDS if k in metrics},
            "tcp_after_dns_seconds": delta("time_connect", "time_namelookup"),
            "tls_after_connect_seconds": delta("time_appconnect", "time_connect"),
            "request_ready_to_first_byte_seconds": delta("time_starttransfer", "time_pretransfer"),
            "first_sse_event_seconds": first_event, "first_visible_text_seconds": first_text,
            "wall_seconds": round(wall, 4), "finish_reasons": finish,
            "model_versions": versions,
            "usage": {k: usage[k] for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount", "serviceTier") if k in usage}}

def probe(key):
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        return {"ok": False, "error": "CURL_UNAVAILABLE"}
    payload = {"contents": [{"parts": [{"text": "Reply with READY."}]}],
               "generationConfig": {"maxOutputTokens": 64,
                                    "thinkingConfig": {"thinkingLevel": "minimal"}}}
    # curl configuration goes through stdin, never argv, a temporary file or stdout.
    config = "\n".join([
        "url = " + json.dumps("https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":streamGenerateContent?alt=sse"),
        "header = " + json.dumps("x-goog-api-key: " + key),
        'header = "Content-Type: application/json"',
        "data = " + json.dumps(json.dumps(payload)), ""])
    start = time.monotonic()
    process = subprocess.Popen([executable, "--silent", "--show-error", "--no-buffer",
                                "--max-time", "30", "--connect-timeout", "10", "--retry", "0",
                                "--write-out", "%{stderr}MM_METRICS %{json}\n", "--config", "-"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr_chunks = []
    reader = threading.Thread(target=lambda: stderr_chunks.append(process.stderr.read(131072)), daemon=True)
    reader.start()
    try:
        process.stdin.write(config.encode())
        process.stdin.close()
        chunks, size, first_event, first_text = [], 0, None, None
        while True:
            line = process.stdout.readline(131073)
            if not line:
                break
            elapsed = round(time.monotonic() - start, 4)
            size += len(line)
            if size > 131072:
                process.kill()
                return {"ok": False, "error": "RESPONSE_BOUND"}
            if not line.startswith(b"data: "):
                continue
            chunk = json.loads(line[6:])
            chunks.append(chunk)
            if first_event is None:
                first_event = elapsed
            if first_text is None and any(p.get("text") and not p.get("thought")
                for c in chunk.get("candidates", []) for p in c.get("content", {}).get("parts", [])):
                first_text = elapsed
        exit_code = process.wait(timeout=5)
        reader.join(timeout=5)
        stderr = b"".join(stderr_chunks).decode(errors="replace")
        metrics = {}
        for line in stderr.splitlines():
            if line.startswith("MM_METRICS "):
                metrics = json.loads(line[len("MM_METRICS "):])
        return summarize(metrics, first_event, first_text, chunks, exit_code, time.monotonic() - start)
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    key = os.environ.get("MOTOMEDIC_GEMINI_API_KEY")
    if not key:
        print(json.dumps({"ok": False, "error": "KEY_UNCONFIGURED"}))
        return 1
    report = {"schema_version": "gemma-timing-v1", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "model": MODEL, "prompt": "synthetic_READY", "max_output_tokens_per_request": 64,
              "thinking_level": "minimal", "automatic_retries": 0,
              "connection_policy": "fresh curl process per request; no deliberate connection reuse",
              "origin": "github_actions" if os.environ.get("GITHUB_ACTIONS") else "local",
              "requests": []}
    for number in range(1, args.requests + 1):
        result = {"request_number": number, **probe(key)}
        report["requests"].append(result)
        print(json.dumps(result), flush=True)
    report["measured_total_tokens"] = sum(r.get("usage", {}).get("totalTokenCount", 0) for r in report["requests"])
    report["usage_missing_requests"] = sum(not r.get("usage") for r in report["requests"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r["ok"] for r in report["requests"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
