import os

os.environ["CREWAI_TRACING_ENABLED"] = "false"

from crews import CvOptimizationCrew


class CvOptimizer:
    """
    Analyser that wraps the CvOptimizationCrew to optimize CVs for specific job postings.
    """

    def optimize(self, cv_path: str, job_posting_path: str, output_directory: str):
        """
        Run CV optimization and write results to output_directory.

        Args:
            job_posting_abspath: Absolute path to the job posting JSON file
            cv_path: Absolute path to the base CV JSON file
            output_directory: Absolute path where the crew writes output files
        """
        inputs = {
            "job_posting_path": job_posting_path,
            "cv_path": cv_path,
            "output_directory": output_directory,
        }

        crew = CvOptimizationCrew()
        crew.crew().kickoff(inputs=inputs)
