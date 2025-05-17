"""
Prompt templates for job analysis.
This module provides templates for LLM prompts used in job analysis.
"""

import re
from typing import Optional

from constants.analysis import AnalysisConstants


class PromptTemplates:
    """Class for managing analysis prompts."""
    
    @staticmethod
    def get_title_analysis_prompt(title: str, company: str, professional_context: str,
                                 relevant_patterns: list, job_titles: Optional[list] = None,
                                 title_match_strictness: float = 0.8) -> str:
        """Generate prompt for job title analysis."""
        return f"""
        You are evaluating if a job title is relevant for {professional_context}.
        
        Job Title: "{title}"
        Company: "{company}"
        
        Relevant title patterns to look for: {', '.join(relevant_patterns)}
        {f"Target job titles: {', '.join(job_titles)}" if job_titles else ""}
        
        Match strictness level: {title_match_strictness} (0-1 scale, where 1 is exact match and 0 is very loose matching)
        
        Provide a JSON object with the following properties:
        - title_keywords: Array of relevant keywords found in the title
        - matches_pattern: Boolean indicating if title matches a relevant pattern
        - pattern_matched: String with the pattern that matched, or null if none
        - estimated_relevance: Float between 0 and 1 indicating relevance
        - reasoning: String with brief explanation of your reasoning
        
        Only respond with the JSON object, no additional text.
        
        IMPORTANT: Use the match strictness level to determine how close the job title needs to be to the target patterns or job titles.
        A high strictness value (e.g., 0.8-1.0) means the job title should closely match the target job titles or patterns.
        A medium strictness value (e.g., 0.5-0.7) allows for some variation and related titles.
        A low strictness value (e.g., 0.1-0.4) means to be very inclusive of roles that might be tangentially related.
        """
    
    @staticmethod
    def get_description_analysis_prompt(title: str, company: str, description: str, 
                                       professional_context: str, required_skills: list,
                                       preferred_skills: list, job_titles: Optional[list] = None,
                                       title_match_strictness: float = 0.8,
                                       relevance_threshold: float = 0.7) -> str:
        """Generate prompt for job description analysis."""
        clean_description = re.sub(r'\s+', ' ', description).strip()
        
        # Truncate description if too long (to stay within token limits)
        max_desc_length = AnalysisConstants.MAX_DESCRIPTION_LENGTH
        if len(clean_description) > max_desc_length:
            clean_description = clean_description[:max_desc_length] + "..."
            
        return f"""
        You are evaluating if a job is relevant for {professional_context}.
        
        Job Title: "{title}"
        Company: "{company}"
        
        Job Description:
        "{clean_description}"
        
        Required skills to look for: {', '.join(required_skills)}
        Preferred skills to look for: {', '.join(preferred_skills)}
        {f"Target job titles: {', '.join(job_titles)}" if job_titles else ""}
        
        Match strictness level: {title_match_strictness} (0-1 scale, where 1 is exact match and 0 is very loose matching)
        Relevance threshold: {relevance_threshold} (Jobs with scores above this are considered relevant)
        
        Provide a JSON object with the following properties:
        - required_skills_found: Array of required skills found in the description
        - preferred_skills_found: Array of preferred skills found in the description
        - missing_required_skills: Array of required skills NOT found
        - job_responsibilities: Array of key job responsibilities
        - relevance_score: Float between 0 and 1 indicating relevance
        - reasoning: String with brief explanation of your reasoning
        
        Only respond with the JSON object, no additional text.
        
        IMPORTANT: Use the match strictness level to determine how close the job needs to match the requirements.
        A high strictness value (e.g., 0.8-1.0) means the job should have most required skills and closely match the target profile.
        A medium strictness value (e.g., 0.5-0.7) allows for a more balanced assessment where some missing skills can be compensated with other factors.
        A low strictness value (e.g., 0.1-0.4) means to be very inclusive and consider many related positions.
        """
