from kabot.agent import cron_fallback_nlp
from kabot.agent.cron_fallback_parts import constants, intent_scoring


def test_cron_fallback_module_reexports_intent_scoring_helpers():
    assert cron_fallback_nlp.REMINDER_KEYWORDS is intent_scoring.REMINDER_KEYWORDS
    assert cron_fallback_nlp.WEATHER_KEYWORDS is intent_scoring.WEATHER_KEYWORDS
    assert cron_fallback_nlp.CRON_MANAGEMENT_OPS is intent_scoring.CRON_MANAGEMENT_OPS
    assert cron_fallback_nlp.CRON_MANAGEMENT_TERMS is intent_scoring.CRON_MANAGEMENT_TERMS
    assert cron_fallback_nlp.score_required_tool_intents is intent_scoring.score_required_tool_intents
    assert (
        cron_fallback_nlp.looks_like_meta_skill_or_workflow_prompt
        is intent_scoring.looks_like_meta_skill_or_workflow_prompt
    )


def test_intent_scoring_uses_constants_submodule():
    assert intent_scoring._LIVE_QUERY_MARKERS is constants._LIVE_QUERY_MARKERS
    assert intent_scoring._META_TOPIC_MARKERS is constants._META_TOPIC_MARKERS
    assert intent_scoring._INTENT_AMBIGUITY_DELTA is constants._INTENT_AMBIGUITY_DELTA
    assert intent_scoring._INTENT_MIN_SCORE is constants._INTENT_MIN_SCORE
    assert intent_scoring._INTENT_STRONG_SCORE is constants._INTENT_STRONG_SCORE
