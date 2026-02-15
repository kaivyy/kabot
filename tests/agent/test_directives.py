"""Tests for inline directives parser."""

import pytest
from kabot.agent.directives import DirectiveParser, ParsedDirectives


def test_parse_think_directive():
    """Test parsing /think directive."""
    parser = DirectiveParser()

    message = "/think What is the capital of France?"
    result = parser.parse(message)

    assert result.has_directives is True
    assert result.think_mode is True
    assert result.cleaned_message == "What is the capital of France?"


def test_parse_verbose_directive():
    """Test parsing /verbose directive."""
    parser = DirectiveParser()

    message = "/verbose Explain how async works"
    result = parser.parse(message)

    assert result.verbose_mode is True
    assert result.cleaned_message == "Explain how async works"


def test_parse_multiple_directives():
    """Test parsing multiple directives."""
    parser = DirectiveParser()

    message = "/think /verbose Solve this problem"
    result = parser.parse(message)

    assert result.think_mode is True
    assert result.verbose_mode is True
    assert result.cleaned_message == "Solve this problem"


def test_parse_no_directives():
    """Test message without directives."""
    parser = DirectiveParser()

    message = "Just a normal message"
    result = parser.parse(message)

    assert result.has_directives is False
    assert result.think_mode is False
    assert result.verbose_mode is False
    assert result.cleaned_message == "Just a normal message"


def test_parse_elevated_directive():
    """Test parsing /elevated directive for extended permissions."""
    parser = DirectiveParser()

    message = "/elevated Run system command"
    result = parser.parse(message)

    assert result.elevated_mode is True
    assert result.cleaned_message == "Run system command"
