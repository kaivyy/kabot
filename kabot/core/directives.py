"""
Directives System for Kabot (Phase 9).

Parses inline commands from message bodies to dynamically control agent behavior.
Directives use the syntax: /directive [args] within the message text.

Examples:
    "Explain quantum physics /think /verbose"
    → Enables chain-of-thought + debug output for this turn
    
    "/model gpt-4 What's the weather?"
    → Forces gpt-4 model for this turn
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Directive pattern: matches /word optionally followed by a value
# e.g., "/think", "/model gpt-4", "/verbose"
_DIRECTIVE_PATTERN = re.compile(
    r"\/([a-zA-Z_]+)(?:\s+([^\s\/]+))?",
)


@dataclass
class DirectiveSet:
    """Parsed directives from a message."""
    
    # Behavior modifiers
    think: bool = False           # Enable chain-of-thought reasoning
    verbose: bool = False         # Enable debug-level output in chat
    elevated: bool = False        # Enable high-risk tool usage
    json_output: bool = False     # Force JSON response format
    no_tools: bool = False        # Disable tool usage for this turn
    raw: bool = False             # Skip markdown formatting

    # Override parameters
    model: str | None = None      # Force specific model
    temperature: float | None = None  # Override temperature
    max_tokens: int | None = None     # Override max tokens

    # System
    debug: bool = False           # Full debug dump
    
    # Raw parsed values
    raw_directives: dict[str, Any] = field(default_factory=dict)


class DirectiveParser:
    """
    Parses directives from message bodies.
    
    Directives are inline commands like /think, /verbose, /model gpt-4
    that modify agent behavior for a single turn.
    """
    
    # Known directives and their types
    KNOWN_DIRECTIVES = {
        "think": "bool",
        "verbose": "bool", 
        "elevated": "bool",
        "json": "bool",
        "notools": "bool",
        "raw": "bool",
        "debug": "bool",
        "model": "str",
        "temp": "float",
        "maxtokens": "int",
    }

    def parse(self, message: str) -> tuple[str, DirectiveSet]:
        """
        Parse directives from a message and return the clean body.
        
        Args:
            message: Raw message text, possibly containing directives.
        
        Returns:
            Tuple of (clean_body, DirectiveSet).
            clean_body has all directive tokens removed.
        """
        if not message:
            return "", DirectiveSet()

        directives = DirectiveSet()
        found_directives: dict[str, Any] = {}
        
        # Find all directive matches
        matches = list(_DIRECTIVE_PATTERN.finditer(message))
        
        for match in matches:
            name = match.group(1).lower()
            value = match.group(2)  # May be None for boolean directives
            
            if name not in self.KNOWN_DIRECTIVES:
                continue  # Skip unknown directives (might be part of code/text)
            
            dtype = self.KNOWN_DIRECTIVES[name]
            
            if dtype == "bool":
                found_directives[name] = True
            elif dtype == "str" and value:
                found_directives[name] = value
            elif dtype == "float" and value:
                try:
                    found_directives[name] = float(value)
                except ValueError:
                    pass
            elif dtype == "int" and value:
                try:
                    found_directives[name] = int(value)
                except ValueError:
                    pass

        # Apply to DirectiveSet
        if found_directives:
            directives.think = found_directives.get("think", False)
            directives.verbose = found_directives.get("verbose", False)
            directives.elevated = found_directives.get("elevated", False)
            directives.json_output = found_directives.get("json", False)
            directives.no_tools = found_directives.get("notools", False)
            directives.raw = found_directives.get("raw", False)
            directives.debug = found_directives.get("debug", False)
            directives.model = found_directives.get("model")
            directives.temperature = found_directives.get("temp")
            directives.max_tokens = found_directives.get("maxtokens")
            directives.raw_directives = found_directives
            
            logger.debug(f"Parsed directives: {found_directives}")

        # Remove directive tokens from message body
        clean_body = message
        for match in reversed(matches):  # Reverse to preserve indices
            name = match.group(1).lower()
            if name in self.KNOWN_DIRECTIVES:
                clean_body = clean_body[:match.start()] + clean_body[match.end():]
        
        clean_body = clean_body.strip()
        # Collapse multiple spaces
        clean_body = re.sub(r"\s{2,}", " ", clean_body)

        return clean_body, directives

    def format_active_directives(self, directives: DirectiveSet) -> str:
        """Format active directives for display."""
        if not directives.raw_directives:
            return ""
        
        parts = []
        if directives.think:
            parts.append("🧠 Think Mode")
        if directives.verbose:
            parts.append("📋 Verbose")
        if directives.json_output:
            parts.append("📦 JSON Output")
        if directives.no_tools:
            parts.append("🚫 No Tools")
        if directives.model:
            parts.append(f"🤖 Model: {directives.model}")
        if directives.debug:
            parts.append("🔍 Debug")
        
        return " | ".join(parts)
