# title_strategy_evaluator.py

import pandas as pd
import numpy as np
import json
import logging
import time
import os
from typing import Dict, Any, List, Tuple
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from services.analysis_strategy import TitleAnalysisStrategy
from utils.factories import AnalysisStrategyFactory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TitleStrategyEvaluator:
    """Evaluator for TitleAnalysisStrategy component."""

    # Define relevance levels and their ranges
    RELEVANCE_LEVELS = {
        "irrelevant": (0.0, 0.2),
        "low": (0.2, 0.4),
        "medium": (0.4, 0.7),
        "high": (0.7, 0.9),
        "very_high": (0.9, 1.0)
    }

    # Order of relevance levels for distance calculation
    LEVEL_ORDER = ["irrelevant", "low", "medium", "high", "very_high"]

    def __init__(self, dataset_path, job_relevance_cutoff=0.7, title_similarity_threshold=0.8):
        """Initialize the evaluator.

        Args:
            dataset_path: Path to the dataset JSON file
            job_relevance_cutoff: Threshold score that determines whether a job is relevant
            title_similarity_threshold: Threshold for title similarity matching
        """
        self.dataset_path = dataset_path
        self.job_relevance_cutoff = job_relevance_cutoff
        self.title_similarity_threshold = title_similarity_threshold

        # Create strategy using factory
        self.strategy = AnalysisStrategyFactory.create_title_strategy()

    def load_test_data(self) -> pd.DataFrame:
        """Load test data from JSON file."""
        try:
            with open(self.dataset_path, 'r') as f:
                test_data = json.load(f)

            # Convert to DataFrame
            df = pd.DataFrame(test_data)
            logger.info(f"Loaded {len(df)} test cases from {self.dataset_path}")
            return df
        except FileNotFoundError:
            logger.error(f"Test data file {self.dataset_path} not found.")
            raise FileNotFoundError(f"Could not find the test data file: {self.dataset_path}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {self.dataset_path}")
            raise ValueError(f"Invalid JSON format in {self.dataset_path}")
        except Exception as e:
            logger.error(f"Error loading test data: {str(e)}")
            raise

    def _get_relevance_level(self, score: float) -> str:
        """Map relevance score to a categorical level."""
        for level, (min_score, max_score) in self.RELEVANCE_LEVELS.items():
            if min_score <= score < max_score:
                return level

        # Handle edge case of score = 1.0
        if score == 1.0:
            return "very_high"

        # Default fallback
        return "irrelevant"

    def _calculate_level_distance(self, expected_level: str, predicted_level: str) -> int:
        """Calculate the distance between two relevance levels."""
        try:
            expected_idx = self.LEVEL_ORDER.index(expected_level)
            predicted_idx = self.LEVEL_ORDER.index(predicted_level)
            return abs(expected_idx - predicted_idx)
        except (ValueError, IndexError):
            logger.error(f"Invalid relevance level: {expected_level} or {predicted_level}")
            return len(self.LEVEL_ORDER) - 1  # Return max distance if error

    def _analyze_single_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single job and return results.

        Args:
            job_data: Dictionary containing job data

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Evaluating title: {job_data['title']}")
        start_time = time.time()

        # Create analysis preferences from job data
        analysis_prefs = {
            "relevant_title_patterns": job_data.get('relevant_patterns', []),
            "title_match_strictness": self.title_similarity_threshold,
            "relevance_threshold": self.job_relevance_cutoff
        }

        try:
            # Call strategy's analyze method
            title_relevance, title_analysis = self.strategy.analyze(
                title=job_data['title'],
                company=job_data['company'],
                analysis_prefs=analysis_prefs,
                job_titles=job_data['job_titles']
            )

            error = None

        except Exception as e:
            logger.error(f"Error analyzing job title '{job_data['title']}': {e}")
            title_relevance = 0.0
            title_analysis = {"error": str(e)}
            error = str(e)

        execution_time_sec = time.time() - start_time

        # Get relevance levels
        expected_level = self._get_relevance_level(job_data['expected_relevance'])
        predicted_level = self._get_relevance_level(title_relevance)

        # Create result record
        result = {
            "title": job_data['title'],
            "company": job_data['company'],
            "expected_relevance": float(job_data['expected_relevance']),
            "actual_relevance": float(title_relevance),
            "expected_relevance_level": expected_level,
            "predicted_relevance_level": predicted_level,
            "level_distance": self._calculate_level_distance(expected_level, predicted_level),
            "execution_time_sec": float(execution_time_sec),
            "error": error,
            "analysis_data": title_analysis
        }

        return result

    def evaluate(self) -> pd.DataFrame:
        """Run evaluation with test data and return results."""
        # Load test data
        test_data = self.load_test_data()

        # Process each test case
        results = []
        for _, row in test_data.iterrows():
            job_data = row.to_dict()
            result = self._analyze_single_job(job_data)
            results.append(result)

        # Create results DataFrame
        results_df = pd.DataFrame(results)
        return results_df

    def calculate_metrics(self, results_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate evaluation metrics from results."""
        # Calculate binary classification metrics
        expected_binary = results_df['expected_relevance'] >= self.job_relevance_cutoff
        predicted_binary = results_df['actual_relevance'] >= self.job_relevance_cutoff

        # Calculate sklearn metrics
        accuracy = float(accuracy_score(expected_binary, predicted_binary))
        precision = float(precision_score(expected_binary, predicted_binary, zero_division=0))
        recall = float(recall_score(expected_binary, predicted_binary, zero_division=0))
        f1 = float(f1_score(expected_binary, predicted_binary, zero_division=0))

        # Calculate level-based metrics
        avg_level_distance = float(results_df['level_distance'].mean())
        level_accuracy = float((results_df['level_distance'] == 0).mean())

        # Calculate average relevance score
        avg_relevance = float(results_df['actual_relevance'].mean())

        # Return metrics as regular Python floats (not numpy types)
        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "avg_relevance": avg_relevance,
            "avg_level_distance": avg_level_distance,
            "level_accuracy": level_accuracy,
            "avg_execution_time_sec": float(results_df['execution_time_sec'].mean())
        }

    def print_evaluation_summary(self, results_df: pd.DataFrame, metrics: Dict[str, float]) -> None:
        """Print a summary of the evaluation results."""
        # Print metrics
        print("\nEvaluation Results:")
        print(f"Total test cases: {len(results_df)}")
        print(f"Binary classification metrics:")
        print(f"  Accuracy: {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  F1 Score: {metrics['f1_score']:.4f}")

        print(f"\nRelevance level metrics:")
        print(f"  Level accuracy: {metrics['level_accuracy']:.4f}")
        print(f"  Average level distance: {metrics['avg_level_distance']:.4f}")

        print(f"\nOther metrics:")
        print(f"  Average relevance score: {metrics['avg_relevance']:.4f}")
        print(f"  Average execution time: {metrics['avg_execution_time_sec']:.4f} seconds")

        # Print individual results
        print("\nDetailed Results:")
        for _, row in results_df.iterrows():
            expected_binary = row['expected_relevance'] >= self.job_relevance_cutoff
            predicted_binary = row['actual_relevance'] >= self.job_relevance_cutoff
            binary_correct = expected_binary == predicted_binary

            binary_result = "✓" if binary_correct else "✗"
            level_distance = row['level_distance']
            level_indicator = "✓" if level_distance == 0 else f"↕{level_distance}"

            print(
                f"{binary_result} {level_indicator} {row['title']} at {row['company']}: "
                f"Expected={row['expected_relevance']:.2f} ({row['expected_relevance_level']}), "
                f"Actual={row['actual_relevance']:.2f} ({row['predicted_relevance_level']})"
            )


def main():
    """Main function to run the evaluation."""
    print("Starting Title Strategy Evaluation")

    # Define the dataset path in an OS-agnostic way
    dataset_path = os.path.join("datasets", "titles_evaluation_dataset.json")

    # Create evaluator with the dataset path
    evaluator = TitleStrategyEvaluator(
        dataset_path=dataset_path,
        job_relevance_cutoff=0.7,
        title_similarity_threshold=0.8
    )

    try:
        # Run evaluation
        results_df = evaluator.evaluate()

        # Calculate metrics
        metrics = evaluator.calculate_metrics(results_df)

        # Print evaluation summary
        evaluator.print_evaluation_summary(results_df, metrics)

        print("\nEvaluation complete!")
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        print("\nPlease make sure the dataset file exists at the specified location.")
    except Exception as e:
        print(f"Error during evaluation: {str(e)}")


if __name__ == "__main__":
    main()