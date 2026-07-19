# <img width="50" height="50" alt="CV-Joint" src="https://github.com/user-attachments/assets/482eb95d-2a4e-4fca-9444-e8a5995952e3" /> CV Joint

Track job postings, create targeted CVs, render them in LaTeX, achieve constant velocity.

## Origins

This started with the idea of combining agentic CV optimization with rendering LaTeX CVs from structured data.

The workflow was originally monolithic, structured data passed internally between agents:

```text
                                                   CurriculumVitae ─┐
                                                                    │
  job posting URL ──▶ [ job posting analyzer ] ──▶ JobPosting ─┐    │
                                                               │    │
                                                               ▼    ▼
     knowledge base ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄▶ [ strategist ] ──▶ CvTransformationPlan
     (RAG retrieval)                                        │
                                                            ▼
                                       [ writer ] ──▶ optimized CurriculumVitae
                                                            │
                                                            ▼
                                       [ LaTeX renderer ] ──▶ PDF
```

Then things began to decompose. Job posting analysis was split from the workflow, CV analysis was added, then a Gradio UI.

The upshot was a job posting/CV tracking system with the ability to optimize CVs for job postings. Structured outputs returned from analysis services are persisted in the file system as pure JSON by a repository service that tracks domain state (*records*, as in  `JobPostingRecord`) in separate collections.

The repository saves a Markdown representation of each object alongside the JSON with its record as front matter.

The status of a job posting is synonymous with its location. The majority of job postings will be under `archived/` or `applied/`.

With the data directory inside a vault, everything is browsable in Obsidian.

Future plans have to do with designing a fully realized CLI and further decomposition.

## Features

RAG chunking, embedding, and search are managed in a separate MCP project; the agents use a connector.

Claude also has this connector, as well as access to the data directory, and they go over CV transformation plans, looking for things the agent missed, discussing things the agent got wrong, and advising when prompts, or the chunking strategy, might want to be tweaked.

- Uses agentic analysis to
  - Create structured data from Job Posting URLs or text files
  - Create structured CV data from text CV files
  - Optimize CV data for a job posting with relevant experience using RAG

## Implementation

- Agentic analysis with CrewAI

- Pydantic for domain objects/structured outputs

- Click CLI

- Gradio tabbed UI

- CVs are rendered using Jinja2 with custom delimiters that play well with LaTeX:

  |              | customized | standard jinja2 |
  | ------------ | ---------- | --------------- |
  | Statements   | `(# #)`    | `{% %}`         |
  | Expressions  | `(( ))`    | `{{ }}`         |
  | Comments     | `%( )%`    | `{# #}`         |
  | Line Comment | `%%`       | `##`            |

## Installation

Runs `uv tool install --editable .`:

```sh
make install
```

## Configuration

Copy `sample.env` to `.env` and set environment variables:

```sh
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GOOGLE_API_KEY=
OPENAI_API_KEY=
SERPER_API_KEY=
```

Configure the `rag-knowledge` MCP server for RAG functions (see below).

Configuration override hierarchy:

1. `src/*/config/settings.yaml` (defaults)
2. `~/.cv-joint/settings.yaml` (user dotfile)
3. `src/*/config/settings.local.yaml` (machine-specific overrides, gitignored)

Example user settings (`~/.cv-joint/settings.yaml`):

```yaml
chat:
  model: "gpt-4o"

mcpServers:
  rag-knowledge: # null in default settings
    command: "~/.local/bin/uv"
    args:
      - "run"
      - "--directory"
      - "~/code/mcp-server-project"
      - "python"
      - "rag_knowledge_mcp.py"
    env:
      LOG_LEVEL: "INFO"
    x-tool-name: "rag_search_knowledge"

crews:
  cv_analysis:
    agents:
      cv_analyst:
        model: gpt-4o
  job_posting_analysis:
    agents:
      job_analyst:
        model: gpt-4o
  cv_optimization:
    agents:
      cv_strategist:
        model: claude-sonnet-4-20250514
      cv_rewriter:
        model: claude-sonnet-4-20250514

repositories:
  filesystem:
    data_dir: "~/vaults/frobozz/areas/job-search/cv-joint"
```

Data directory structure:

```
{data_dir}/
├── collections/
│   ├── job-postings.json
│   ├── cvs.json
│   └── optimized-cvs.json
├── job-postings/
│   ├── {identifier}/                 # active/unfiled job posting
│   │   ├── job-posting.json
│   │   ├── job-posting.md
│   │   └── cvs/{identifier}/         # optimized for job posting
│   │       ├── curriculum-vitae.json
│   │       ├── curriculum-vitae.md
│   │       ├── cv-transformation-plan.json
│   │       └── cv-transformation-plan.md
│   └── {location}/{identifier}/      # applied, archived, or custom location
│       ├── job-posting.json
│       ├── job-posting.md
│       └── cvs/{identifier}/
│           ├── curriculum-vitae.json
│           ├── curriculum-vitae.md
│           ├── cv-transformation-plan.json
│           └── cv-transformation-plan.md
└── cvs/{identifier}/
    ├── curriculum-vitae.json
    └── curriculum-vitae.md
```

## Testing

```sh
make test
```

runs `uv run pytest tests/ --tb=short`

## Gradio Usage

```sh
cv-joint
```

Launches Gradio, runs `GRADIO_LAUNCHED_COMMAND`, `GRADIO_FINISHED_COMMAND` after Ctl-C

(I have it launch a wrapper pointing at `http://localhost:7860`, then close it)

```sh
cv-joint open
```

Launches Gradio then opens the default browser at `http://localhost:7860`

## CLI Usage

```sh
# UI
cv-joint           # serve at http://localhost:7860
cv-joint open      # serve and open in browser

# Job postings
cv-joint list job-postings
cv-joint list job-postings/applied
cv-joint list job-postings/archived
cv-joint list job-postings --all
cv-joint list job-postings -q acme
cv-joint transition job-postings/{id} {location}
cv-joint archive job-postings/{id}
cv-joint unarchive job-postings/{id}
cv-joint apply job-postings/{id} {cv-id}
cv-joint apply job-postings/{id} {cv-id} --date 2026-05-27
cv-joint reanalyze job-postings/{id}

# CVs
cv-joint list cvs
cv-joint list cvs -q wesley
cv-joint reanalyze cvs/{id} path/to/file

# General
cv-joint remove job-postings/{id}
cv-joint remove job-postings/{id}/cvs/{id}
cv-joint rename job-postings/{id} {new-id}
cv-joint export-markdown
cv-joint export-markdown [job-postings|cvs|optimizations]
cv-joint show-config
```
