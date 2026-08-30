"""
The recorded response cache, which is what protects the reproducibility gate.

A judge with no AWS account and no API key runs --mode replay, the recordings
answer, and the headline number comes out the same. These tests hold that promise
in place.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cloudfix.model import ModelClient, ModelError, ModelResponse, estimate_cost_usd  # noqa: E402


class CacheBehaviour(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def client(self, mode="auto", model="test-model"):
        return ModelClient(model=model, mode=mode, cache_dir=self.directory)

    def record(self, client, system, user, text="recorded"):
        key = client._key(system, user, 2000, 0.0)
        response = ModelResponse(
            text=text, model=client.model, input_tokens=10, output_tokens=5,
            latency_seconds=1.25, from_cache=False,
        )
        client._write_cache(key, response, system, user)
        return key

    def test_a_recorded_response_is_replayed_without_a_call(self):
        client = self.client(mode="replay")
        self.record(client, "sys", "user")
        response = client.complete("sys", "user")
        self.assertEqual(response.text, "recorded")
        self.assertTrue(response.from_cache)
        self.assertEqual(client.calls_made, 0)

    def test_replay_with_nothing_recorded_fails_loudly_rather_than_inventing(self):
        client = self.client(mode="replay")
        with self.assertRaises(ModelError):
            client.complete("sys", "never recorded")

    def test_measured_latency_survives_the_cache(self):
        client = self.client(mode="replay")
        self.record(client, "sys", "user")
        self.assertEqual(client.complete("sys", "user").latency_seconds, 1.25)

    def test_a_different_prompt_is_a_different_key(self):
        client = self.client()
        self.assertNotEqual(
            client._key("sys", "a", 2000, 0.0), client._key("sys", "b", 2000, 0.0)
        )

    def test_the_same_prompt_is_the_same_key_across_clients(self):
        self.assertEqual(
            self.client()._key("sys", "a", 2000, 0.0),
            self.client()._key("sys", "a", 2000, 0.0),
        )

    def test_the_first_sample_keeps_the_original_key(self):
        """A nonce added unconditionally would invalidate every recording ever made."""
        client = self.client()
        without = client._key("sys", "a", 2000, 0.0)
        client.nonce = ""
        self.assertEqual(client._key("sys", "a", 2000, 0.0), without)
        client.nonce = "2"
        self.assertNotEqual(client._key("sys", "a", 2000, 0.0), without)

    def test_the_manifest_records_which_model_produced_the_recordings(self):
        client = self.client()
        self.record(client, "sys", "user")
        with open(os.path.join(self.directory, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["model"], "test-model")

    def test_replay_picks_up_the_recorded_model_when_none_is_named(self):
        seed = self.client()
        self.record(seed, "sys", "user")
        judge = ModelClient(model=None, mode="replay", cache_dir=self.directory)
        self.assertEqual(judge.model, "test-model")
        self.assertEqual(judge.complete("sys", "user").text, "recorded")

    def test_a_corrupt_cache_file_is_a_miss_not_a_crash(self):
        client = self.client(mode="auto")
        key = client._key("sys", "user", 2000, 0.0)
        with open(os.path.join(self.directory, key + ".json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(client._read_cache(key))

    def test_an_unknown_mode_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            ModelClient(mode="whatever", cache_dir=self.directory)


class CostArithmetic(unittest.TestCase):
    def test_a_million_input_tokens_costs_the_input_rate(self):
        self.assertAlmostEqual(estimate_cost_usd(1000000, 0), 3.0, places=6)

    def test_a_million_output_tokens_costs_the_output_rate(self):
        self.assertAlmostEqual(estimate_cost_usd(0, 1000000), 15.0, places=6)

    def test_nothing_costs_nothing(self):
        self.assertEqual(estimate_cost_usd(0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
