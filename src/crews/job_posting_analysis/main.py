#!/usr/bin/env python
"""
Run the JobPostingAnalysis crew from the command line.

Usage:
    uv run python -m crews.job_posting_analysis.main <url>
    JOB_URL=<url> uv run python -m crews.job_posting_analysis.main

With crewai CLI (add entry point to pyproject.toml first):
    JOB_URL=<url> crewai run
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """Run the crew and output JSON to stdout."""
    from .crew import JobPostingAnalysisCrew

    url = os.environ.get("JOB_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)

    if not url:
        print(__doc__)
        sys.exit(1)

    inputs = {
        "job_posting_url": url,
        "content_file": os.environ.get("CONTENT_FILE"),
    }

    crew = JobPostingAnalysisCrew()
    result = crew.crew().kickoff(inputs=inputs)

    if result.pydantic is None:
        print("Error: crew did not return a pydantic model", file=sys.stderr)
        sys.exit(1)

    print(result.pydantic.model_dump_json(indent=2))


if __name__ == "__main__":
    run()
