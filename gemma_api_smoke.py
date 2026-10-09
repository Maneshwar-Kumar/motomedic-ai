"""One synthetic Gemma API call. Reads GitHub secret via environment only."""
import json
import os
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Redirect rejected")

def main():
    key = os.environ.get("MOTOMEDIC_GEMINI_API_KEY")
    if not key:
        print(json.dumps({"ok": False, "error": "KEY_UNCONFIGURED"}))
        return 1
    payload = {"contents": [{"parts": [{"text": "Reply with READY."}]}],
               "generationConfig": {"maxOutputTokens": 256,
                                    "thinkingConfig": {"thinkingLevel": "minimal"}}}
    request = Request("https://generativelanguage.googleapis.com/v1beta/models/"
                      "gemma-4-31b-it:streamGenerateContent?alt=sse",
                      data=json.dumps(payload).encode(),
                      headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    start = time.monotonic()
    try:
        chunks, size = [], 0
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            while True:
                line = response.readline(131073)
                if not line:
                    break
                size += len(line)
                if size > 131072 or time.monotonic() - start > 30:
                    raise RuntimeError("Response bound exceeded")
                if line.startswith(b"data: "):
                    chunks.append(json.loads(line[6:]))
        candidates = [c for chunk in chunks for c in chunk.get("candidates", [])]
        ready = any("READY" in p.get("text", "") for c in candidates
                    for p in c.get("content", {}).get("parts", []) if not p.get("thought"))
        stopped = any(c.get("finishReason") == "STOP" for c in candidates)
        matches = bool(chunks) and all(c.get("modelVersion") == "gemma-4-31b-it" for c in chunks)
        ok = ready and stopped and matches
        print(json.dumps({"ok": ok, "model": "gemma-4-31b-it",
                          "elapsed_seconds": round(time.monotonic() - start, 2),
                          "usage": chunks[-1].get("usageMetadata") if chunks else None}))
        return 0 if ok else 1
    except Exception as exc:
        # Never print exception messages, response bodies, keys or generated text.
        print(json.dumps({"ok": False, "error_type": type(exc).__name__,
                          "http_status": getattr(exc, "code", None)}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
