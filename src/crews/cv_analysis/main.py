#!/usr/bin/env python
"""
Run the CvAnalysis crew from the command line.

Usage:
    uv run python -m crews.cv_analysis.main <cv_path>
    CV_PATH=<path> uv run python -m crews.cv_analysis.main

With crewai CLI (add entry point to pyproject.toml first):
    CV_PATH=<path> crewai run
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """Run the crew and output JSON to stdout."""
    from .crew import CvAnalysisCrew

    cv_path = os.environ.get("CV_PATH") or (sys.argv[1] if len(sys.argv) > 1 else None)

    if not cv_path:
        print(__doc__)
        sys.exit(1)

    inputs = {
        "candidate_cv_path": cv_path,
    }

    crew = CvAnalysisCrew()
    result = crew.crew().kickoff(inputs=inputs)

    if result.pydantic is None:
        print("Error: crew did not return a pydantic model", file=sys.stderr)
        sys.exit(1)

    print(result.pydantic.model_dump_json(indent=2))


if __name__ == "__main__":
    run()
