from kabot.core.context_engine import ContextEngine, LegacyContextEngine
from kabot.session.manager import Session


def test_context_engine_interface_exists():
    engine = LegacyContextEngine()

    assert isinstance(engine, ContextEngine)
    assert callable(getattr(engine, "compile", None))


def test_legacy_context_engine_compiles_session_history():
    session = Session(
        key="cli:direct",
        messages=[
            {"role": "user", "content": "halo", "timestamp": "1"},
            {"role": "assistant", "content": "hai", "timestamp": "2"},
        ],
    )

    engine = LegacyContextEngine(max_messages=1)

    assert engine.compile(session) == [{"role": "assistant", "content": "hai"}]
