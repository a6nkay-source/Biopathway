import json
import tempfile
import time
import unittest
from pathlib import Path

from _helpers import FakeClock, FakeTransport
from bpm.http import HttpClient, SourceError

URL = "https://example.org/api"


def client(tmp, transport, **kw):
    clock = FakeClock()
    http = HttpClient(cache_dir=Path(tmp), transport=transport, sleep=clock.sleep,
                      clock=clock.clock, **kw)
    return http, clock


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_cache_hit_skips_network(self):
        t = FakeTransport({"example": [(200, '{"a": 1}')]})
        http, _ = client(self.tmp, t)
        self.assertEqual(http.get_json("uniprot", URL, {"q": "x"}), {"a": 1})
        self.assertEqual(http.get_json("uniprot", URL, {"q": "x"}), {"a": 1})
        self.assertEqual(len(t.calls), 1)
        self.assertEqual([r["cached"] for r in http.log], [False, True])

    def test_param_order_does_not_change_cache_key(self):
        t = FakeTransport({"example": [(200, "ok")]})
        http, _ = client(self.tmp, t)
        http.get("kegg", URL, {"b": 2, "a": 1})
        http.get("kegg", URL, {"a": 1, "b": 2})
        self.assertEqual(len(t.calls), 1)

    def test_retries_transient_errors(self):
        t = FakeTransport({"example": [(503, ""), (429, ""), (200, "done")]})
        http, clock = client(self.tmp, t)
        self.assertEqual(http.get("string", URL), "done")
        self.assertEqual(len(t.calls), 3)
        self.assertTrue(any(s >= 1 for s in clock.sleeps))  # exponential backoff happened

    def test_404_is_not_retried(self):
        t = FakeTransport({"example": [(404, "")]})
        http, _ = client(self.tmp, t)
        with self.assertRaises(SourceError) as cm:
            http.get("reactome", URL)
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(len(t.calls), 1)

    def test_network_failure_raises_source_error(self):
        t = FakeTransport({"example": [OSError("dns")]})
        http, _ = client(self.tmp, t, max_retries=1)
        with self.assertRaises(SourceError) as cm:
            http.get("ncbi", URL)
        self.assertIn("network error", cm.exception.message)
        self.assertEqual(len(t.calls), 2)

    def test_stale_cache_used_when_live_call_fails(self):
        t = FakeTransport({"example": [(200, "old")]})
        http, _ = client(self.tmp, t)
        http.get("kegg", URL)
        # Age the entry past its TTL.
        path = next(Path(self.tmp).glob("*.json"))
        entry = json.loads(path.read_text())
        entry["fetched_epoch"] = time.time() - 10 * 86400
        path.write_text(json.dumps(entry))
        t2 = FakeTransport({"example": [(500, "")]})
        http2, _ = client(self.tmp, t2, max_retries=0)
        self.assertEqual(http2.get("kegg", URL), "old")
        self.assertTrue(http2.log[-1]["stale"])

    def test_offline_without_cache_fails_cleanly(self):
        http, _ = client(self.tmp, FakeTransport({}), offline=True)
        with self.assertRaises(SourceError):
            http.get("kegg", URL)

    def test_rate_limit_spaces_requests(self):
        t = FakeTransport({"example": [(200, "x")]})
        http, clock = client(self.tmp, t, use_cache=False)
        http.get("string", URL + "/1")
        http.get("string", URL + "/2")
        self.assertAlmostEqual(sum(clock.sleeps), 1.0, places=5)  # STRING: 1 request/s

    def test_secret_params_stay_out_of_log_and_cache(self):
        t = FakeTransport({"example": [(200, "x")]})
        http, _ = client(self.tmp, t)
        http.get("ncbi", URL, {"db": "gene"}, secret_params={"api_key": "SECRET"})
        self.assertIn("api_key=SECRET", t.calls[0])
        self.assertNotIn("SECRET", json.dumps(http.log))
        for f in Path(self.tmp).glob("*.json"):
            self.assertNotIn("SECRET", f.read_text())

    def test_invalid_json_is_source_error(self):
        http, _ = client(self.tmp, FakeTransport({"example": [(200, "<html>")]}))
        with self.assertRaises(SourceError):
            http.get_json("uniprot", URL)


if __name__ == "__main__":
    unittest.main()
