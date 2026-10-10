"""Per-operation engineering event stream; technical events follow verified commits.

Integration transport is SSE. Authenticated operation ownership remains the hosted
API's responsibility. This module never receives raw provider token fragments.
"""
from copy import deepcopy
import json
import queue
import threading


class VerifiedDeliveryStream:
    def __init__(self, max_blocks=64):
        if type(max_blocks) is not int or not 1 <= max_blocks <= 64:
            raise ValueError("Invalid stream bound")
        self.events = queue.Queue(maxsize=max_blocks + 1)
        self.lock, self.next_block, self.closed = threading.Lock(), 0, False
        self.max_blocks, self.session_id, self.version = max_blocks, None, None

    def deliver(self, packet):
        # Caller is the trusted runtime, invoked only after semantic/exact checks,
        # scope recheck and durable session+delivery record. Never accept client flags.
        needed = {"session_id", "session_version", "block", "texts", "citations", "content_sha256", "architecture"}
        if type(packet) is not dict or set(packet) != needed:
            raise ValueError("Invalid verified delivery packet")
        if (type(packet["texts"]) is not list or not packet["texts"] or
                any(type(t) is not str or not t or len(t) > 8000 for t in packet["texts"]) or
                type(packet["block"]) is not int or type(packet["session_version"]) is not int or
                not packet["citations"]):
            raise ValueError("Invalid verified delivery packet")
        with self.lock:
            if self.closed or packet["block"] != self.next_block or self.next_block >= self.max_blocks:
                raise ValueError("Closed or unordered stream")
            if self.session_id is not None and (packet["session_id"], packet["session_version"]) != (self.session_id, self.version):
                raise ValueError("Stream operation changed")
            self.session_id, self.version = packet["session_id"], packet["session_version"]
            self.events.put_nowait({"event": "verified_block", "id": self.next_block,
                                   "data": deepcopy(packet)})
            self.next_block += 1

    def finish(self, result):
        # Transport terminates distinctly after a partial failure. No exception body.
        with self.lock:
            if self.closed: raise ValueError("Stream already closed")
            self.closed = True
            event = "complete" if result["route"] == "SUPPORTED" else "error"
            self.events.put_nowait({"event": event, "id": self.next_block, "data": {
                "route": result["route"], "delivered_blocks": self.next_block,
                "partial_verified_delivery": self.next_block > 0 and event == "error",
                "engineering_sink_only": True}})

    def iter_events(self, timeout_seconds=180):
        while True:
            try: event = self.events.get(timeout=timeout_seconds)
            except queue.Empty:
                # Consumer timeout doesn't cancel/re-execute the underlying operation.
                yield {"event": "heartbeat", "id": None, "data": {}}
                continue
            yield event
            if event["event"] in ("complete", "error"): return

    def iter_sse(self, timeout_seconds=180):
        for event in self.iter_events(timeout_seconds):
            if event["event"] == "heartbeat": yield b": heartbeat\n\n"
            else:
                data = json.dumps(event["data"], ensure_ascii=False, allow_nan=False)
                yield ("id: " + str(event["id"]) + "\nevent: " + event["event"] +
                       "\ndata: " + data + "\n\n").encode("utf-8")
