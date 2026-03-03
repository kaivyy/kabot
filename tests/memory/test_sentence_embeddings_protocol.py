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
