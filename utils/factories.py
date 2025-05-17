"""
Factory classes for creating service components.
This module provides factories to decouple object creation from usage.
"""

import logging
from typing import Optional, Any

from config import Config
from services.analysis_strategy import (
    AnalysisStrategy,
    TitleAnalysisStrategy,
    DescriptionAnalysisStrategy
)
from services.database_service import DatabaseService
from services.job_analysis_service import JobAnalysisService
from services.llm_json_parser import LLMJsonParser
from services.llm_provider import LLMProvider, OpenAIProvider
from services.prompt_templates import PromptTemplates

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create_openai_provider(api_key: Optional[str] = None,
                               model: Optional[str] = None) -> LLMProvider:
        """
        Create an OpenAI provider with the specified API key and model.

        Args:
            api_key: API key for OpenAI, defaults to Config.OPENAI_API_KEY
            model: Model name, defaults to Config.OPENAI_MODEL

        Returns:
            LLMProvider: An instance of OpenAIProvider
        """
        if api_key is None:
            api_key = Config.OPENAI_API_KEY

        if model is None:
            model = Config.OPENAI_MODEL

        logger.info(f"Creating OpenAIProvider with model {model}")
        return OpenAIProvider(api_key=api_key, model=model)


class ParserFactory:
    """Factory for creating parsers."""

    @staticmethod
    def create_llm_json_parser() -> LLMJsonParser:
        """
        Create an LLM JSON parser.

        Returns:
            LLMJsonParser: An instance of LLMJsonParser
        """
        logger.info("Creating LLMJsonParser")
        return LLMJsonParser()


class TemplateFactory:
    """Factory for creating prompt templates."""

    @staticmethod
    def create_prompt_templates() -> PromptTemplates:
        """
        Create prompt templates.

        Returns:
            PromptTemplates: An instance of PromptTemplates
        """
        logger.info("Creating PromptTemplates")
        return PromptTemplates()


class AnalysisStrategyFactory:
    """Factory for creating analysis strategies."""

    @staticmethod
    def create_title_strategy(llm_provider: Optional[LLMProvider] = None,
                              prompt_templates: Optional[PromptTemplates] = None,
                              json_parser: Optional[LLMJsonParser] = None) -> AnalysisStrategy:
        """
        Create a title analysis strategy.

        Args:
            llm_provider: LLM provider for generating completions, defaults to OpenAIProvider with config settings
            prompt_templates: Prompt templates for analysis, defaults to a new PromptTemplates instance
            json_parser: JSON parser for parsing LLM responses, defaults to a new LLMJsonParser instance

        Returns:
            AnalysisStrategy: An instance of TitleAnalysisStrategy
        """
        if llm_provider is None:
            llm_provider = LLMProviderFactory.create_openai_provider()

        if prompt_templates is None:
            prompt_templates = TemplateFactory.create_prompt_templates()

        if json_parser is None:
            json_parser = ParserFactory.create_llm_json_parser()

        logger.info("Creating TitleAnalysisStrategy")
        return TitleAnalysisStrategy(
            llm_provider=llm_provider,
            prompt_templates=prompt_templates,
            json_parser=json_parser
        )

    @staticmethod
    def create_description_strategy(llm_provider: Optional[LLMProvider] = None,
                                    prompt_templates: Optional[PromptTemplates] = None,
                                    json_parser: Optional[LLMJsonParser] = None) -> AnalysisStrategy:
        """
        Create a description analysis strategy.

        Args:
            llm_provider: LLM provider for generating completions, defaults to OpenAIProvider with config settings
            prompt_templates: Prompt templates for analysis, defaults to a new PromptTemplates instance
            json_parser: JSON parser for parsing LLM responses, defaults to a new LLMJsonParser instance

        Returns:
            AnalysisStrategy: An instance of DescriptionAnalysisStrategy
        """
        if llm_provider is None:
            llm_provider = LLMProviderFactory.create_openai_provider()

        if prompt_templates is None:
            prompt_templates = TemplateFactory.create_prompt_templates()

        if json_parser is None:
            json_parser = ParserFactory.create_llm_json_parser()

        logger.info("Creating DescriptionAnalysisStrategy")
        return DescriptionAnalysisStrategy(
            llm_provider=llm_provider,
            prompt_templates=prompt_templates,
            json_parser=json_parser
        )


class JobAnalysisServiceFactory:
    """Factory for creating job analysis services."""

    @staticmethod
    def create_job_analysis_service(title_analyzer: Optional[AnalysisStrategy] = None,
                                    description_analyzer: Optional[AnalysisStrategy] = None,
                                    db_service: Optional[DatabaseService] = None) -> JobAnalysisService:
        """
        Create a job analysis service.

        Args:
            title_analyzer: Strategy for analyzing job titles, defaults to a new TitleAnalysisStrategy
            description_analyzer: Strategy for analyzing job descriptions, defaults to a new DescriptionAnalysisStrategy
            db_service: Database service for storing analysis results, defaults to a new DatabaseService

        Returns:
            JobAnalysisService: An instance of JobAnalysisService
        """
        if title_analyzer is None:
            title_analyzer = AnalysisStrategyFactory.create_title_strategy()

        if description_analyzer is None:
            description_analyzer = AnalysisStrategyFactory.create_description_strategy()

        if db_service is None:
            db_service = DatabaseService()

        logger.info("Creating JobAnalysisService")
        return JobAnalysisService(
            title_analyzer=title_analyzer,
            description_analyzer=description_analyzer,
            db_service=db_service
        )

    @staticmethod
    def create_default_job_analysis_service() -> JobAnalysisService:
        """
        Create a job analysis service with all default components.
        This is a convenience method that creates a fully configured service
        with no parameters needed.

        Returns:
            JobAnalysisService: A fully configured JobAnalysisService instance
        """
        logger.info("Creating default JobAnalysisService with all dependencies")
        return JobAnalysisServiceFactory.create_job_analysis_service()


class AnalysisServiceFactory:
    """Factory for creating a complete analysis service with all dependencies."""

    @staticmethod
    def create_analysis_service() -> Any:
        """
        Create a complete analysis service with all required components.
        Import is done inside function to avoid circular imports.

        Returns:
            AnalysisService: A fully configured analysis service
        """
        # Import inside method to avoid circular imports
        from services.analysis_service import AnalysisService

        logger.info("Creating complete AnalysisService with dependencies")

        # Return a new analysis service that will use the factories internally
        return AnalysisService()