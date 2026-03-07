from io import StringIO
from types import SimpleNamespace

from kabot.memory.sentence_embeddings import SentenceEmbeddingProvider


def test_send_request_ignores_non_json_stdout_lines(monkeypatch):
    provider = SentenceEmbeddingProvider(model="all-MiniLM-L6-v2", auto_unload_seconds=0)
    provider._req_counter = 0

    fake_stdout = StringIO(
        "Warning: noisy line from dependency\n"
        "{\"id\": \"req_1\", \"status\": \"ok\", \"result\": [0.1, 0.2, 0.3]}\n"
    )
    fake_stdin = StringIO()
    provider._process = SimpleNamespace(
        stdin=fake_stdin,
        stdout=fake_stdout,
        poll=lambda: None,
    )

    monkeypatch.setattr(provider, "_start_subprocess", lambda: None)

    result = provider._send_request("embed", "hello")
    assert result == [0.1, 0.2, 0.3]


def test_start_subprocess_uses_quiet_env_and_devnull_stderr(monkeypatch):
    provider = SentenceEmbeddingProvider(model="all-MiniLM-L6-v2", auto_unload_seconds=0)
    calls: dict[str, object] = {}

    class _FakeProcess:
        def __init__(self):
            self.stdin = StringIO()
            self.stdout = StringIO('{"id": "init", "status": "ok"}\n')
            self.pid = 4321

        def poll(self):
            return None

    def _fake_popen(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr("kabot.memory.sentence_embeddings.subprocess.Popen", _fake_popen)

    provider._start_subprocess()

    kwargs = calls["kwargs"]
    env = kwargs["env"]
    assert kwargs["stderr"] == __import__("subprocess").DEVNULL
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert env["TOKENIZERS_PARALLELISM"] == "false"
    assert env["TRANSFORMERS_VERBOSITY"] == "error"
    assert env["HF_HUB_DISABLE_TELEMETRY"] == "1"
