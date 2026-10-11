"""Autonomous Claude arm: no deterministic response correction or routing."""
import json
import time

TASK = """Manage this rider conversation yourself using the cached manual and policy.
Do not assume a condition without asking when it changes the documented action.
Keep typed observations separate from attempts. Use NOT_TRIED, OBSERVED_NORMAL,
OBSERVED_ABNORMAL, ACTION_COMPLETED_UNRESOLVED, NOT_APPLICABLE, UNCLEAR, RESOLVED.
Return only JSON with these fields:
type: SUPPORTED|AMBIGUOUS|UNSUPPORTED|SAFETY_STOP|SYSTEM_ERROR;
natural_language: concise rider-facing text including required warnings;
cited_pages: array of objects {pdf_page: physical source page number};
clarification_question: one question or null;
suggested_step_id: short descriptive action identifier or null;
escalation_uri: mailto:support@royalenfield.com or null;
session_state: {observations: array, attempted_actions: array of {action, outcome}}.
Do not add unsupported repairs or infer hidden faults. Stop at support when no
documented successor is established. Never repeat a previously unresolved action.
This is a private engineering test; no source images or excerpts are delivered.
"""


def messages_for_turn(case, turn_index, previous_outputs=None):
    messages = []
    for i in range(turn_index + 1):
        text = case['user_turns'][i]['text']
        messages.append({'role': 'user', 'content': TASK + '\nRider: ' + text if i == 0 else text})
        if i < turn_index:
            content = previous_outputs[i] if previous_outputs is not None else '.'
            messages.append({'role': 'assistant', 'content': content})
    return messages


def run_cases(transport, cases, pass_id):
    rows = []
    for case in cases:
        previous = []
        for turn_index, turn in enumerate(case['user_turns']):
            begin = time.perf_counter()
            try:
                result = transport.complete_messages(messages_for_turn(case, turn_index, previous),
                                                     max_tokens=1800,
                                                     tag=f"B:{pass_id}:{case['record_id']}:{turn_index}")
                output = result['output']
                # Preserve malformed raw output for scoring; never repair/retry it.
                previous.append(result['raw_text'] or 'No response returned.')
                error = None if isinstance(output, dict) else 'INVALID_JSON_OUTPUT'
                calls = [result]
            except Exception as exc:
                output, calls = None, []
                error = type(exc).__name__
                previous.append('No assistant response was available due to a system error.')
            elapsed = time.perf_counter() - begin
            rows.append({'arm': 'B_CLAUDE_MANAGED', 'pass_id': pass_id,
                         'record_id': case['record_id'], 'turn_index': turn_index,
                         'user_input': turn['text'], 'output': output,
                         'provider_calls': calls, 'provider_request_count': len(calls),
                         'rider_visible_total_seconds': elapsed,
                         'rider_visible_ttft_seconds': elapsed,
                         'rider_visible_streaming': False,
                         'provider_ttft_seconds': [c.get('ttft_seconds') for c in calls],
                         'controlled_error_class': error,
                         'deterministic_output_correction': False,
                         'golden_evaluator_expectations_used_in_prompts': False})
    return rows
