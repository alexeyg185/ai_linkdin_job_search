"""
LLM provider interfaces and implementations.
This module provides abstractions for interacting with language models.
"""

import httpx
from abc import ABC, abstractmethod
from openai import OpenAI

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate_completion(self, prompt: str, **kwargs) -> str:
        """Generate a completion from the LLM."""
        pass

class OpenAIProvider(LLMProvider):
    """Implementation of LLMProvider using OpenAI's API."""
    
    def __init__(self, api_key: str, model: str):
        """Initialize the provider with API key and model."""

        self.client = OpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(60.0, connect=30.0),
            max_retries=3,
        )
        self.model = model
    
    def generate_completion(self, prompt: str, **kwargs) -> str:
        """Generate a completion using OpenAI's API."""
        system_message = kwargs.get('system_message', 
                                   "You are a job relevance analyzer that helps determine if job listings match a user's preferences.")
        temperature = kwargs.get('temperature', 0.1)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            seed=kwargs.get('seed', 42),
        )
        
        return response.choices[0].message.content.strip()
