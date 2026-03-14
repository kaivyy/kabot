from types import SimpleNamespace

from kabot.core.directives import DirectiveParser


def test_persist_directives_stores_full_runtime_state_and_saves_session():
    from kabot.agent.loop_core.directive_pipeline import persist_directives

    parser = DirectiveParser()
    clean_body, directives = parser.parse(
        "/think /verbose /json /notools /raw /debug /model gpt-4 /temp 0.3 /maxtokens 400 answer me"
    )
    assert clean_body == "answer me"

    saves: list[object] = []
    loop = SimpleNamespace(
        directive_parser=parser,
        sessions=SimpleNamespace(save=lambda session: saves.append(session)),
    )
    session = SimpleNamespace(metadata={})

    directive_state = persist_directives(loop, session, directives)

    assert directive_state == session.metadata["directives"]
    assert session.metadata["directives"] == {
        "think": True,
        "verbose": True,
        "elevated": False,
        "json_output": True,
        "no_tools": True,
        "raw": True,
        "debug": True,
        "model": "gpt-4",
        "temperature": 0.3,
        "max_tokens": 400,
        "raw_directives": {
            "think": True,
            "verbose": True,
            "json": True,
            "notools": True,
            "raw": True,
            "debug": True,
            "model": "gpt-4",
            "temp": 0.3,
            "maxtokens": 400,
        },
    }
    assert saves == [session]


def test_apply_directive_overrides_sets_message_model_override_metadata():
    from kabot.agent.loop_core.directive_pipeline import apply_directive_overrides

    parser = DirectiveParser()
    _clean_body, directives = parser.parse("/model gpt-5-mini hello there")
    msg = SimpleNamespace(metadata={})

    apply_directive_overrides(msg, directives)

    assert msg.metadata["model_override"] == "gpt-5-mini"
    assert msg.metadata["model_override_source"] == "directive"
