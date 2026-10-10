"""Offline contract checks; these do not establish live latency or semantic quality."""
from copy import deepcopy
from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from architecture_benchmark import (BlockDecoder, partition, reconstruct, check_texts,
    ValidationFailure, run_sample, Allocation, MAX_CALLS, MODEL)
from approved_registry import ApprovedEvidenceRegistry
from approved_text_journeys import SimulatedRetrieval
from generation_providers import ProviderResult, gemma_runtime_config, ProviderFailure
from test_approved_integration import INDEX, ROOT
from session_store import SQLiteSessionStore


class Judge:
    def __init__(self, output):
        self.output = output
        self.last_telemetry = None
    def complete(self, policy, payload, schema):
        return ProviderResult(self.output, 2, 1, telemetry={"software_double": True})


class BenchmarkContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def allowed(self, rid):
        step = self.registry.step(self.registry._consumer.routes[rid]["step_id"])
        return {"step_id": step.step_id, "kind": step.kind, "claims": [
            {"claim_id": c["claim_id"], "wording": [c["text"]],
             "role": c["response_role"], "evidence_ids": c["evidence_ids"]} for c in step.claims]}

    def test_mirror_caution_and_action_stay_inseparable(self):
        for rid in ("GEN003", "EXP003"):
            allowed = self.allowed(rid)
            self.assertEqual(partition(allowed), [list(range(len(allowed["claims"])))] )

    def test_only_source_reviewed_phone_conditions_split(self):
        allowed = self.allowed("GEN026")
        self.assertEqual(partition(allowed), [[0], [1]])
        allowed["claims"].reverse()
        with self.assertRaises(ValidationFailure):
            partition(allowed)

    def test_other_fact_pairs_do_not_implicitly_split(self):
        self.assertEqual(partition(self.allowed("GEN006")), [[0, 1]])

    def test_incremental_decoder_emits_only_complete_blocks(self):
        delivered = []
        parser = BlockDecoder(2, lambda i,t: delivered.append((i,t)))
        parser.feed('{"blocks":[{"texts":["condition: a')
        self.assertEqual(delivered, [])
        parser.feed('b"]}')
        self.assertEqual(delivered, [(0,["condition: ab"])])
        parser.feed(',{"texts":["second"]}]}')
        self.assertEqual(delivered, [(0,["condition: ab"]),(1,["second"])])

    def test_decoder_all_possible_splits_with_unicode_and_escaped_quotes(self):
        import json
        text = json.dumps({"blocks":[{"texts":["é \\\" brace }"]},{"texts":["second"]}]},ensure_ascii=False)
        for i in range(len(text)+1):
            delivered = []
            parser = BlockDecoder(2, lambda n,t: delivered.append(t))
            parser.feed(text[:i])
            parser.feed(text[i:])
            self.assertEqual(len(delivered),2)

    def test_decoder_rejects_extra_block(self):
        parser = BlockDecoder(1, lambda *_:None)
        with self.assertRaises(ValidationFailure):
            parser.feed('{"blocks":[{"texts":["one"]},{"texts":["two"]}]}')

    def test_decoder_rejects_model_citations_or_extra_fields(self):
        parser = BlockDecoder(1, lambda *_:None)
        with self.assertRaises(ValidationFailure):
            parser.feed('{"blocks":[{"texts":["one"],"page":99}]}')

    def test_reconstruction_preserves_server_owned_claim_citations(self):
        allowed = self.allowed("GEN003")
        output = reconstruct(allowed,[c["wording"][0] for c in allowed["claims"]])
        self.assertEqual([c["evidence_ids"] for c in output],[c["evidence_ids"] for c in allowed["claims"]])
        with self.assertRaises(ValidationFailure):
            reconstruct(allowed,["missing caution"])

    def test_completeness_failure_rejects_even_supported_claim(self):
        allowed = self.allowed("GEN003")
        judge = Judge({"supported":[True,True],"complete":[True,False],"unsupported_additions":False})
        with self.assertRaises(ValidationFailure):
            check_texts(judge,self.registry,allowed,[0,1],["a","b"])

    def test_supported_false_or_additions_reject(self):
        allowed = self.allowed("GEN003")
        for output in ({"supported":[True,False],"complete":[True,True],"unsupported_additions":False},
                       {"supported":[True,True],"complete":[True,True],"unsupported_additions":True}):
            with self.assertRaises(ValidationFailure):
                check_texts(Judge(output),self.registry,allowed,[0,1],["a","b"])

    def test_verifier_cardinality_must_match(self):
        with self.assertRaises(ValidationFailure):
            check_texts(Judge({"supported":[True],"complete":[True],"unsupported_additions":False}),
                        self.registry,self.allowed("GEN003"),[0,1],["a","b"])

    def test_total_allocation_is_finite(self):
        allocation = Allocation()
        provider = Judge({})
        for _ in range(MAX_CALLS):
            allocation.invoke(provider,"",{}, {})
        with self.assertRaises(ProviderFailure):
            allocation.invoke(provider,"",{}, {})

    def test_component_route_commits_before_delivery(self):
        class Select:
            def __init__(self,*args,**kwargs): pass
            def complete(self,policy,payload,schema):
                return ProviderResult({"choices":[0]*len(payload["claims"])},2,4,
                                      telemetry={"software_double":True})
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteSessionStore(Path(temp)/"sessions.sqlite")
            store.db.execute("CREATE TABLE benchmark_deliveries (session_id TEXT, block INTEGER, session_version INTEGER, content_sha256 TEXT, evidence_ids TEXT)")
            try:
                with patch('architecture_benchmark.BoundedProvider',Select):
                    row = run_sample(self.registry,SimulatedRetrieval(INDEX),gemma_runtime_config(MODEL),
                                     Allocation(),store,'EXP003','explicit centred','A_COMPONENT_SELECTION')
                self.assertEqual(row['route'],'SUPPORTED')
                self.assertTrue(row['session_saved_before_first_delivery'])
                self.assertEqual(store.db.execute('SELECT count(*) FROM benchmark_deliveries').fetchone()[0],1)
                self.assertNotIn('explicit centred',str(row))
            finally:
                store.close()

    def test_bad_selection_releases_nothing(self):
        class BadSelect:
            def __init__(self,*args,**kwargs): pass
            def complete(self,*args): return ProviderResult({"choices":[99,99]})
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteSessionStore(Path(temp)/"sessions.sqlite")
            store.db.execute("CREATE TABLE benchmark_deliveries (session_id TEXT, block INTEGER, session_version INTEGER, content_sha256 TEXT, evidence_ids TEXT)")
            try:
                with patch('architecture_benchmark.BoundedProvider',BadSelect):
                    row=run_sample(self.registry,SimulatedRetrieval(INDEX),gemma_runtime_config(MODEL),
                                   Allocation(),store,'GEN003','private','A_COMPONENT_SELECTION')
                self.assertEqual(row['route'],'SYSTEM_ERROR')
                self.assertIsNone(row['first_verified_output_seconds'])
                self.assertEqual(store.db.execute('SELECT count(*) FROM benchmark_deliveries').fetchone()[0],0)
            finally:
                store.close()


class RedactedDiagnostics(unittest.TestCase):
    def test_diagnostics_never_record_strings_or_arbitrary_field_names(self):
        from architecture_benchmark import output_diagnostics
        out=output_diagnostics({"texts":["PRIVATE RAW TEXT"],"SECRET_UNKNOWN_FIELD":"PRIVATE", "supported":[True,"PRIVATE"], "choices":[0,1]})
        self.assertNotIn("PRIVATE",str(out))
        self.assertNotIn("SECRET_UNKNOWN_FIELD",str(out))
        self.assertEqual(out["unknown_top_level_field_count"],1)
        self.assertEqual(out["supported"]["boolean_values"],[True,None])
        self.assertEqual(out["choices"]["integer_values"],[0,1])

    def test_cardinality_schema_is_bounded_without_mutating_shared_schema(self):
        from architecture_benchmark import sized_schema,CHECK_SCHEMA
        schema=sized_schema(CHECK_SCHEMA,"supported",2)
        self.assertEqual(schema["properties"]["supported"]["minItems"],2)
        self.assertEqual(schema["properties"]["supported"]["maxItems"],2)
        self.assertNotIn("minItems",CHECK_SCHEMA["properties"]["supported"])


class StreamReleaseContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ApprovedEvidenceRegistry.load(ROOT, INDEX)

    def run_stream(self, *, terminal_failure=False, judge_reject=False, invalid_thought=False, delivery_stream=None):
        import json
        import time
        import threading
        from architecture_benchmark import BLOCK_SCHEMA, CHECK_SCHEMA
        committed = threading.Event()
        streamed = {"blocks":[{"texts":["Connected: only hour format can be selected."]},
                              {"texts":["Disconnected: Set Time is available."]}]}
        class Provider:
            def __init__(self,*args,transport=None,**kwargs): self.transport=transport
            def complete(self,policy,payload,schema):
                if "blocks" in schema["properties"]:
                    self.transport(MODEL,'fake-key',{},30)
                    if terminal_failure:
                        raise ProviderFailure('PROVIDER_SERVICE_ERROR')
                    return ProviderResult(streamed,2,10,telemetry={"software_double":True})
                if "supported" in schema["properties"]:
                    n=len(payload['claims'])
                    return ProviderResult({"supported":[not judge_reject]*n,
                                           "complete":[True]*n,"unsupported_additions":False},2,3,
                                          telemetry={"software_double":True})
                raise AssertionError('Unexpected schema')
        def transport(model,key,payload,timeout,callback):
            if invalid_thought:
                callback({"modelVersion":MODEL,"candidates":[{"content":{"parts":[{"text":"","thought":1}]}}]})
            first='{"blocks":['+json.dumps(streamed['blocks'][0])
            callback({"modelVersion":MODEL,"candidates":[{"content":{"parts":[{"text":first}]}}]})
            if not judge_reject:
                self.assertTrue(committed.wait(3),'First complete block must commit while generator remains open')
            time.sleep(0.08)
            if terminal_failure:
                raise ProviderFailure('PROVIDER_SERVICE_ERROR')
            rest=','+json.dumps(streamed['blocks'][1])+']}'
            callback({"modelVersion":MODEL,"candidates":[{"content":{"parts":[{"text":rest}]}}]})
            return [], {"software_double":True}
        class DB:
            def __init__(self,db):self.db=db
            def execute(self,sql,*args):
                result=self.db.execute(sql,*args)
                if sql.startswith('INSERT INTO benchmark_deliveries'):
                    committed.set()
                return result
            def close(self):self.db.close()
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteSessionStore(Path(temp)/'sessions.sqlite')
            store.db.execute('CREATE TABLE benchmark_deliveries (session_id TEXT, block INTEGER, session_version INTEGER, content_sha256 TEXT, evidence_ids TEXT)')
            store.db=DB(store.db)
            try:
                with patch('architecture_benchmark.BoundedProvider',Provider),patch('benchmark_stream_transport.stream_request',transport):
                    row=run_sample(self.registry,SimulatedRetrieval(INDEX),gemma_runtime_config(MODEL),
                                   Allocation(),store,'GEN026','private-input','C_VERIFIED_STREAM_BLOCKS',
                                   delivery_stream=delivery_stream)
                count=store.db.execute('SELECT count(*) FROM benchmark_deliveries').fetchone()[0]
                return row,count
            finally:store.close()

    def test_first_verified_block_commits_while_generator_still_open(self):
        row,count=self.run_stream()
        self.assertEqual(row['route'],'SUPPORTED')
        self.assertEqual(count,2)
        self.assertTrue(row['verification_time_overlaps_generation'])
        self.assertLess(row['first_verified_output_seconds'],row['complete_response_seconds'])
        self.assertEqual([b['block'] for b in row['delivered_blocks']],[0,1])

    def test_terminal_failure_preserves_partial_delivery_without_supported_result(self):
        row,count=self.run_stream(terminal_failure=True)
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(count,1)
        self.assertTrue(row['partial_verified_delivery_before_failure'])
        self.assertIsNone(row['complete_response_seconds'])

    def test_rejected_first_block_never_delivers(self):
        row,count=self.run_stream(judge_reject=True)
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(count,0)
        self.assertIsNone(row['first_verified_output_seconds'])

    def test_numeric_thought_flag_rejected_before_any_delivery(self):
        row,count=self.run_stream(invalid_thought=True)
        self.assertEqual(row['route'],'SYSTEM_ERROR')
        self.assertEqual(count,0)

    def test_duplicate_stream_key_rejected_before_callback(self):
        delivered=[]
        parser=BlockDecoder(1,lambda *x:delivered.append(x))
        with self.assertRaises(ValidationFailure):
            parser.feed('{"blocks":[{"texts":["first"],"texts":["second"]}]}')
        self.assertEqual(delivered,[])


if __name__ == '__main__':
    unittest.main()
