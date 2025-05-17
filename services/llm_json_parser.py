"""
JSON parser for LLM outputs.
This module provides a specialized parser for handling JSON from LLM responses.
"""

import json
import re
from typing import Dict, Any

class LLMJsonParser:
    """
    Lightweight JSON parser specifically designed for LLM outputs.
    Handles common LLM JSON formatting issues.
    """

    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM output, handling common formatting issues.

        Args:
            text: Text containing JSON from an LLM

        Returns:
            Parsed JSON as a dictionary

        Raises:
            ValueError: If JSON parsing fails after all attempts
        """
        # First, attempt to find JSON in markdown code blocks
        code_block_pattern = r"```(?:json)?(.*?)```"
        code_blocks = re.findall(code_block_pattern, text, re.DOTALL)

        if code_blocks:
            # Try each extracted code block
            for block in code_blocks:
                try:
                    return json.loads(block.strip())
                except json.JSONDecodeError:
                    continue

        # Try to find JSON between curly braces if no code blocks worked
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            pass

        # Last resort: try to parse the raw text
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM output: {str(e)}")
