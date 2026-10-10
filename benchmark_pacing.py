"""Experimental shared admission; configured limits are NOT verified account quotas."""
from collections import deque
import json
import threading
import time


POLICY = {
    "version": "conservative-experimental-pacing-v1",
    "active_project_quotas_verified": False,
    "requests_per_rolling_minute": 6,
    "minimum_request_spacing_seconds": 10,
    "input_token_reservation_per_rolling_minute": 12000,
    "token_reservation_method": "UTF8_JSON_BYTES_PLUS_1024_PROTOCOL_ALLOWANCE_NOT_TOKENIZER_COUNT",
    "maximum_admission_wait_seconds": 125,
    "pretrial_cooldown_seconds": 60,
    "maximum_transient_retries_total": 2,
    "maximum_retries_per_nonstream_call": 1,
    "stream_retries": 0,
    "daily_remaining_quota_verified": False,
    "maximum_requests_this_run": 18,
    "other_project_clients_coordinated": False,
}


class AdmissionFailure(Exception):
    pass


class Admission:
    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self.lock, self.history = threading.Lock(), deque()

    def admit(self, policy, payload, schema):
        # Include schema and prompt, reserve separately from output-token limits.
        reserved = len(json.dumps([policy, payload, schema], ensure_ascii=False,
                                  allow_nan=False).encode("utf-8")) + 1024
        limit = POLICY["input_token_reservation_per_rolling_minute"]
        if reserved > limit:
            raise AdmissionFailure("INPUT_RESERVATION_EXCEEDS_EXPERIMENT_LIMIT")
        begin = self.clock()
        while True:
            with self.lock:
                now = self.clock()
                while self.history and now - self.history[0][0] >= 60:
                    self.history.popleft()
                wait = 0
                if self.history:
                    wait = max(0, self.history[-1][0] + 10 - now)
                if len(self.history) >= 6 or sum(x[1] for x in self.history) + reserved > limit:
                    wait = max(wait, self.history[0][0] + 60 - now)
                if wait <= 0:
                    self.history.append((now, reserved))
                    return {"admission_wait_seconds": now - begin,
                            "reserved_input_tokens_estimate": reserved,
                            "requests_in_rolling_minute": len(self.history),
                            "reserved_input_tokens_in_rolling_minute": sum(x[1] for x in self.history)}
            if self.clock() - begin + wait > POLICY["maximum_admission_wait_seconds"]:
                raise AdmissionFailure("ADMISSION_WAIT_BOUND")
            self.sleep(wait)
