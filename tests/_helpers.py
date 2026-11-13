import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURE_CACHE = ROOT / "tests" / "fixtures" / "cache"


class FakeTransport:
    """Scripted transport: `routes` maps a URL substring to a list of responses.

    A response is (status, body) or an Exception instance to raise. The last
    response for a route repeats once the list is exhausted.
    """

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        for key, responses in self.routes.items():
            if key in url:
                item = responses.pop(0) if len(responses) > 1 else responses[0]
                if isinstance(item, Exception):
                    raise item
                status, body = item
                return status, {}, body
        raise OSError(f"no route for {url}")


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
