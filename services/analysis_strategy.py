import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple

from constants.analysis import AnalysisConstants
from services.llm_json_parser import LLMJsonParser
from services.llm_provider import LLMProvider
from services.prompt_templates import PromptTemplates

logger = logging.getLogger(__name__)


class ProfessionalContextHelper:
    @staticmethod
    def get_professional_context(job_titles: List[str]) -> str:
        """
        Generate a description of the professional context based on the user's job title preferences.

        Args:
            job_titles: List of job titles the user is interested in

        Returns:
            context: A string describing the professional context
        """
        if not job_titles:
            return "a professional in your field of interest"

        # If there's only one job title
        if len(job_titles) == 1:
            return f"a {job_titles[0]}"

        # For multiple job titles, create a more complex description
        # Extract common words to identify the general field
        common_words = set()
        for title in job_titles:
            words = set(word.lower() for word in title.split())
            if common_words:
                common_words = common_words.intersection(words)
            else:
                common_words = words

        # If we found common words, use them to describe the field
        if common_words and len(common_words) > 0:
            field_words = " ".join(common_words)
            return f"a professional in the {field_words} field"

        # If no common words or too many titles, list them
        if len(job_titles) <= 3:
            titles_text = ", ".join(job_titles[:-1]) + " or " + job_titles[-1]
            return f"a professional looking for roles such as {titles_text}"

        # If there are too many titles, summarize
        return f"a professional interested in roles like {', '.join(job_titles[:3])} and similar positions"


class AnalysisStrategy(ABC):
    @abstractmethod
    def analyze(self, **kwargs) -> Tuple[float, Dict[str, Any]]:
        pass


class TitleAnalysisStrategy(AnalysisStrategy):
    def __init__(self, llm_provider: LLMProvider, prompt_templates: PromptTemplates, json_parser: LLMJsonParser):
        self.llm_provider = llm_provider
        self.prompt_templates = prompt_templates
        self.json_parser = json_parser
        self.max_retries = 3
        self.retry_delay = 2
        logger.info("TitleAnalysisStrategy initialized")

    def analyze(self, **kwargs) -> Tuple[float, Dict[str, Any]]:
        title = kwargs.get('title')
        company = kwargs.get('company')
        analysis_prefs = kwargs.get('analysis_prefs', {})
        job_titles = kwargs.get('job_titles', [])
        logger.info(f"Analyzing title='{title}' for company='{company}'")

        prompt = self.prompt_templates.get_title_analysis_prompt(
            title=title,
            company=company,
            professional_context=ProfessionalContextHelper.get_professional_context(job_titles),
            relevant_patterns=analysis_prefs.get('relevant_title_patterns', []),
            job_titles=job_titles,
            title_match_strictness=analysis_prefs.get('title_match_strictness',
                                                      AnalysisConstants.DEFAULT_TITLE_MATCH_STRICTNESS)
        )

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Title analysis attempt {attempt + 1}")
                content = self.llm_provider.generate_completion(prompt)
                analysis = self.json_parser.parse(content)
                score = analysis.get('estimated_relevance', 0.0)
                logger.info(f"Title analysis successful with score={score}")
                return score, analysis
            except ValueError as e:
                logger.error(f"JSON parse error on title analysis: {e}")
                raise
            except Exception as e:
                logger.warning(f"Title analysis attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    backoff = self.retry_delay * (2 ** attempt)
                    time.sleep(backoff + backoff * 0.2 * random.random())
                else:
                    logger.error("All title analysis retries failed")
                    return 0.0, {"estimated_relevance": 0.0, "reasoning": "API error", "error": str(e)}


class DescriptionAnalysisStrategy(AnalysisStrategy):
    def __init__(self, llm_provider: LLMProvider, prompt_templates: PromptTemplates, json_parser: LLMJsonParser):
        self.llm_provider = llm_provider
        self.prompt_templates = prompt_templates
        self.json_parser = json_parser
        self.max_retries = 3
        self.retry_delay = 2
        logger.info("DescriptionAnalysisStrategy initialized")

    def analyze(self, **kwargs) -> Tuple[float, Dict[str, Any]]:
        title = kwargs.get('title')
        company = kwargs.get('company')
        description = kwargs.get('description')
        analysis_prefs = kwargs.get('analysis_prefs', {})
        job_titles = kwargs.get('job_titles', [])
        logger.info(f"Analyzing description for title='{title}', company='{company}'")

        prompt = self.prompt_templates.get_description_analysis_prompt(
            title=title,
            company=company,
            description=description,
            professional_context=ProfessionalContextHelper.get_professional_context(job_titles),
            required_skills=analysis_prefs.get('required_skills', []),
            preferred_skills=analysis_prefs.get('preferred_skills', []),
            job_titles=job_titles,
            title_match_strictness=analysis_prefs.get('title_match_strictness',
                                                      AnalysisConstants.DEFAULT_TITLE_MATCH_STRICTNESS),
            relevance_threshold=analysis_prefs.get('relevance_threshold', AnalysisConstants.DEFAULT_RELEVANCE_THRESHOLD)
        )

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Description analysis attempt {attempt + 1}")
                content = self.llm_provider.generate_completion(prompt)
                analysis = self.json_parser.parse(content)
                score = analysis.get('relevance_score', 0.0)
                logger.info(f"Description analysis successful with score={score}")
                return score, analysis
            except ValueError as e:
                logger.error(f"JSON parse error on description analysis: {e}")
                raise
            except Exception as e:
                logger.warning(f"Description analysis attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    backoff = self.retry_delay * (2 ** attempt)
                    time.sleep(backoff + backoff * 0.2 * random.random())
                else:
                    logger.error("All description analysis retries failed")
                    return 0.0, {"relevance_score": 0.0, "reasoning": "API error", "error": str(e)}
