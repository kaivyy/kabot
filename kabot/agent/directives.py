"""Inline directives parser for power-user control."""

import re
from dataclasses import dataclass

from loguru import logger


@dataclass
class ParsedDirectives:
    """Result of parsing directives from a message."""
    has_directives: bool = False
    think_mode: bool = False
    verbose_mode: bool = False
    elevated_mode: bool = False
    cleaned_message: str = ""


class DirectiveParser:
    """
    Parses inline directives from user messages.

    Supported directives:
    - /think: Enable extended reasoning mode
    - /verbose: Enable detailed explanations
    - /elevated: Grant extended permissions (use with caution)
    """

    DIRECTIVE_PATTERN = re.compile(r'^(/\w+)\s*')

    DIRECTIVES = {
        "/think": "think_mode",
        "/verbose": "verbose_mode",
        "/elevated": "elevated_mode",
    }

    def parse(self, message: str) -> ParsedDirectives:
        """
        Parse directives from message.

        Args:
            message: User message potentially containing directives

        Returns:
            ParsedDirectives with flags and cleaned message
        """
        result = ParsedDirectives()
        cleaned = message

        # Iteratively match directives at the start of the string
        while True:
            match = self.DIRECTIVE_PATTERN.match(cleaned)
            if not match:
                break

            directive = match.group(1)
            directive_lower = directive.lower()

            if directive_lower in self.DIRECTIVES:
                result.has_directives = True
                attr_name = self.DIRECTIVES[directive_lower]
                setattr(result, attr_name, True)
                logger.debug(f"Directive detected: {directive}")
            else:
                # Unknown directive - warn and stop processing
                logger.warning(f"Unknown directive: {directive}")
                break

            # Remove the matched directive and whitespace from the start
            cleaned = cleaned[match.end():].strip()

        # Validate cleaned message is not empty after directive removal
        if result.has_directives and not cleaned:
            logger.warning("Message is empty after directive removal, keeping original")
            result.cleaned_message = message
        else:
            result.cleaned_message = cleaned

        return result
