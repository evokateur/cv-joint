# <img width="50" height="50" alt="CV-Joint" src="https://github.com/user-attachments/assets/482eb95d-2a4e-4fca-9444-e8a5995952e3" /> CV Joint

Track job postings, create targeted CVs, render them in LaTeX, achieve constant velocity.

## Origins

This started with the idea of combining an agentic workflow for CV optimization with rendering LaTeX CVs from structured CV output.

The workflow was originally monolithic, structured outputs passed internally between stages in the pipeline:

```text
  job posting (URL / text) ─────▶ [ job analysis ]  ──▶ JobPosting ─┐
                                                                     │
  base CV (text) ───────────────▶ [ CV analysis ]   ──▶ CurriculumVitae ─┐
                                                                     │    │
                                                                     ▼    ▼
   knowledge base ┄┄┄┄┄┄┄┄┄┄┄┄┄▶ [ strategist ] ──▶ CvTransformationPlan
    (RAG retrieval)                                          │
                                                             ▼
                                       [ writer ] ──▶ optimized CurriculumVitae
                                                             │
                                                             ▼
                                       [ LaTeX renderer ] ──▶ PDF
```

Then things began to decompose, the workflow broken down into separate steps, the idea being that each persists structured output to be used by subsequent steps in the pipeline. Currently, job and CV analysis run independently, producing data to be used later to create optimized CVs. All three types are persisted to the filesystem as JSON, alongside a markdown rendering that also shows up in the Gradio UI.

## Features

- Uses agentic analysis to
  - Create structured data from Job Posting URLs or text files
  - Create structured CV data from text CV files
  - Optimize CV data for a job posting with relevant experience using RAG
- Generates Markdown versions of domain objects, suitable for Obsidian
- Renders CV data in LaTeX to generate PDFs

## Implementation

- Agentic analysis with CrewAI

- Pydantic for domain objects and structured outputs

- Click CLI

- Gradio tabbed UI

- CVs are rendered using Jinja2 with custom delimiters that play well with LaTeX:

  |              | customized | standard jinja2 |
  | ------------ | ---------- | --------------- |
  | Statements   | `(# #)`    | `{% %}`         |
  | Expressions  | `(( ))`    | `{{ }}`         |
  | Comments     | `%( )%`    | `{# #}`         |
  | Line Comment | `%%`       | `##`            |

Simplified project structure:

```sh
.
├── src
│   ├── renderers
│   │   └── latex # LaTeX PDF rendering
│   ├── config
│   ├── crews
│   │   ├── cv_analysis
│   │   ├── cv_optimization
│   │   ├── job_posting_analysis
│   │   └── tools
│   ├── infrastructure
│   ├── models
│   ├── renderers
│   │   └── latex
│   ├── repositories
│   │   └── filesystem.py
│   ├── services
│   │   └── analyzers # crew facades
│   │   └── application.py
│   │   └── converters.py
│   │   └── exporter.py
│   │   └── knowledge_chat.py
│   └── ui
│   │   └── app.py # Gradio
│   │   └── cli.py
└── templates
    ├── cover-letter.tex
    └── cv.tex
```

## Installation

```sh
make install
```

runs `uv tool install --editable .`

## Configuration

```sh
cp sample.env .env
```

Set environment variables in `.env`:

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

Strings beginning with `~/` will undergo tilde expansion.

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
