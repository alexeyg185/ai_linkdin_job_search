"""
Dataset handling for job analysis experiments.
This module provides functionality for loading and managing job datasets.
"""

import logging
import json
import csv
from typing import Dict, List, Any, Set, Optional, Tuple
from enum import Enum, auto
from dataclasses import dataclass

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class RelevanceCategory(Enum):
    """Relevance categories for job classification."""
    TITLE_NOT_RELEVANT = auto()
    DESCRIPTION_NOT_RELEVANT = auto()
    DESCRIPTION_RELEVANT = auto()
    UNKNOWN = auto()

@dataclass
class JobDataset:
    """Dataset of jobs with ground truth labels."""
    jobs: List[Dict[str, Any]]
    labels: Dict[str, RelevanceCategory]
    metadata: Dict[str, Any]
    
    @property
    def size(self) -> int:
        """Get the number of jobs in the dataset."""
        return len(self.jobs)
    
    @property
    def category_counts(self) -> Dict[RelevanceCategory, int]:
        """Get counts of jobs by relevance category."""
        counts = {category: 0 for category in RelevanceCategory}
        for category in self.labels.values():
            counts[category] += 1
        return counts
    
    def get_jobs_by_category(self, category: RelevanceCategory) -> List[Dict[str, Any]]:
        """Get all jobs in a specific category."""
        return [job for job in self.jobs if self.labels.get(job['job_id']) == category]
    
    def to_file(self, file_path: str) -> None:
        """Save dataset to a file."""
        data = {
            "metadata": self.metadata,
            "labels": {job_id: label.name for job_id, label in self.labels.items()},
            "jobs": self.jobs
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def from_file(cls, file_path: str) -> 'JobDataset':
        """Load dataset from a file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert label strings back to enum values
        labels = {
            job_id: RelevanceCategory[label_str] 
            for job_id, label_str in data.get("labels", {}).items()
        }
        
        return cls(
            jobs=data.get("jobs", []),
            labels=labels,
            metadata=data.get("metadata", {})
        )
    
    def export_to_csv(self, file_path: str) -> None:
        """Export dataset to CSV for easy viewing."""
        fieldnames = ["job_id", "title", "company", "relevance_category"]
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for job in self.jobs:
                writer.writerow({
                    "job_id": job.get("job_id", ""),
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "relevance_category": self.labels.get(job.get("job_id", ""), 
                                                         RelevanceCategory.UNKNOWN).name
                })


class DatasetHandler:
    """Handler for loading and managing job datasets."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize with optional DB manager."""
        self.db_manager = db_manager or DatabaseManager()
    
    def load_jobs_by_ids(self, job_ids: List[str]) -> List[Dict[str, Any]]:
        """Load specific jobs by their IDs."""
        jobs = []
        
        for job_id in job_ids:
            job = self.db_manager.get_one(
                f"SELECT * FROM job_listings WHERE job_id = ?", 
                (job_id,)
            )
            if job:
                jobs.append(dict(job))
            else:
                logger.warning(f"Job with ID {job_id} not found in database")
        
        return jobs
    
    def load_labeled_dataset(self, dataset_file: str) -> JobDataset:
        """Load a labeled dataset from a file."""
        return JobDataset.from_file(dataset_file)
    
    def create_dataset_with_labels(self, 
                                  jobs: List[Dict[str, Any]], 
                                  labels: Dict[str, RelevanceCategory],
                                  metadata: Optional[Dict[str, Any]] = None) -> JobDataset:
        """Create a dataset with provided jobs and labels."""
        return JobDataset(
            jobs=jobs,
            labels=labels,
            metadata=metadata or {}
        )
    
    def create_dataset_from_query(self, query: str, params: tuple = (), 
                                 labels: Optional[Dict[str, RelevanceCategory]] = None) -> JobDataset:
        """Create a dataset from a database query."""
        jobs = self.db_manager.execute_query(query, params)
        
        # Convert row objects to dictionaries
        jobs = [dict(job) for job in jobs]
        
        # If no labels provided, set all to UNKNOWN
        if labels is None:
            labels = {job['job_id']: RelevanceCategory.UNKNOWN for job in jobs}
        
        return JobDataset(
            jobs=jobs,
            labels=labels,
            metadata={
                "source": "database_query",
                "query": query,
                "size": len(jobs)
            }
        )
    
    def create_balanced_dataset(self, 
                              category_counts: Dict[RelevanceCategory, int],
                              seed: Optional[int] = None) -> JobDataset:
        """
        Create a balanced dataset with specified number of jobs in each category.
        
        This requires having pre-labeled jobs in the system or using heuristics.
        """
        import random
        if seed is not None:
            random.seed(seed)
        
        all_jobs = []
        labels = {}
        
        # For each category, fetch the requested number of jobs
        for category, count in category_counts.items():
            if category == RelevanceCategory.TITLE_NOT_RELEVANT:
                # Find jobs with titles unlikely to be relevant
                # This is a heuristic - in practice you'd want better criteria
                query = """
                SELECT j.* FROM job_listings j
                WHERE LOWER(j.title) NOT LIKE '%engineer%'
                AND LOWER(j.title) NOT LIKE '%developer%'
                AND LOWER(j.title) NOT LIKE '%scientist%'
                LIMIT ?
                """
                category_jobs = self.db_manager.execute_query(query, (count,))
                
            elif category == RelevanceCategory.DESCRIPTION_NOT_RELEVANT:
                # Find jobs that passed title filter but description wasn't relevant
                # This requires having analyzed jobs already
                query = """
                SELECT j.* FROM job_listings j
                JOIN job_states s ON j.job_id = s.job_id
                WHERE s.state = 'irrelevant'
                LIMIT ?
                """
                category_jobs = self.db_manager.execute_query(query, (count,))
                
            elif category == RelevanceCategory.DESCRIPTION_RELEVANT:
                # Find jobs that were marked as relevant
                query = """
                SELECT j.* FROM job_listings j
                JOIN job_states s ON j.job_id = s.job_id
                WHERE s.state = 'relevant'
                LIMIT ?
                """
                category_jobs = self.db_manager.execute_query(query, (count,))
                
            else:
                # Unknown category
                logger.warning(f"Unknown category {category}, skipping")
                continue
            
            # Convert row objects to dictionaries
            category_jobs = [dict(job) for job in category_jobs]
            
            # Add jobs to dataset
            all_jobs.extend(category_jobs)
            
            # Add labels
            for job in category_jobs:
                labels[job['job_id']] = category
        
        # Shuffle jobs
        random.shuffle(all_jobs)
        
        return JobDataset(
            jobs=all_jobs,
            labels=labels,
            metadata={
                "source": "balanced_dataset",
                "category_counts": {category.name: count for category, count in category_counts.items()},
                "size": len(all_jobs)
            }
        )
