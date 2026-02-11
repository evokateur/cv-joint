#!/usr/bin/env python
"""
Run the CvOptimization crew from the command line.

Usage:
    uv run python -m crews.cv_optimization.main <job_posting_path> <cv_path> [output_dir]
    JOB_POSTING_PATH=<path> CV_PATH=<path> uv run python -m crews.cv_optimization.main

With crewai CLI (add entry point to pyproject.toml first):
    JOB_POSTING_PATH=<path> CV_PATH=<path> crewai run

Paths should point to JSON files containing serialized JobPosting and CurriculumVitae models.
OUTPUT_DIR controls where output files are written (defaults to a temp directory).
"""
import os
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """Run the crew and output JSON to stdout."""
    from .crew import CvOptimizationCrew

    job_posting_path = os.environ.get("JOB_POSTING_PATH") or (
        sys.argv[1] if len(sys.argv) > 1 else None
    )
    cv_path = os.environ.get("CV_PATH") or (
        sys.argv[2] if len(sys.argv) > 2 else None
    )

    if not job_posting_path or not cv_path:
        print(__doc__)
        sys.exit(1)

    output_directory = os.environ.get("OUTPUT_DIR") or (
        sys.argv[3] if len(sys.argv) > 3 else None
    )
    if not output_directory:
        output_directory = tempfile.mkdtemp()

    inputs = {
        "job_posting_path": job_posting_path,
        "cv_path": cv_path,
        "output_directory": output_directory,
    }

    crew = CvOptimizationCrew()
    result = crew.crew().kickoff(inputs=inputs)

    if result.pydantic is None:
        print("Error: crew did not return a pydantic model", file=sys.stderr)
        sys.exit(1)

    print(result.pydantic.model_dump_json(indent=2))


if __name__ == "__main__":
    run()
