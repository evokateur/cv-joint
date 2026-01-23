#!/bin/bash

tree -I 'pytest.ini|llm-context|requirements.txt|sample.env|tests|_docs|docs|data|job_postings|vector_*|db|__pycache__|knowledge-base|__init__*|examples|*.aux|*.log|*.md|Makefile|output|*.sh|*.out|*.ipynb|*.lock|*.egg-info|scripts|utils' | sed '$d; $d' | tee >(pbcopy)

echo "(copied to paste buffer)"
