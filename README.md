# <img width="50" height="50" alt="CV-Joint" src="https://github.com/user-attachments/assets/482eb95d-2a4e-4fca-9444-e8a5995952e3" /> CV Joint

Track job postings, create targeted CVs, render them in LaTeX, achieve constant velocity.

## What this is and how it got there

This started with the idea of combining agentic CV optimization with rendering LaTeX CVs from structured data.

The agentic workflow was originally monolithic, with structured data passed internally between agents:

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

Then things began to decompose. Job posting analysis was split from the pipeline, CV analysis was added, then a Gradio UI.

The upshot was a job posting/CV tracking system with the ability to optimize CVs.

Structured outputs returned from analysis services are persisted as JSON by a repository service that tracks domain state in separate collections of *record* (e.g. `JobPostingRecord`) objects.

The repository also writes a Markdown representation of each object (alongside the JSON) with its record as front matter.

```markdown
---
identifier: labcorp-backend-engineer-i
path: job-postings/archived/labcorp-backend-engineer-i
url: https://careers.labcorp.com/global/en/job/26813
company: Labcorp
title: Backend Engineer I
experience_level: Entry to Mid-level
applied_at: null
applied_with: null
is_archived: true
location: archived
transitions:
- date: '2026-06-20T00:20:22.059312'
  location: archived
created_at: '2026-02-13T02:03:53.572088'
updated_at: '2026-06-20T00:20:22.059312'
---
# Backend Engineer I at Labcorp
**Original Posting:** [https://careers.labcorp.com/global/en/job/26813](https://careers.labcorp.com/global/en/job/26813)
...
```

Data directory structure:
<details>
<summary>Data directory structure</summary>

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

</details>

With the data directory inside a vault, everything is browsable in Obsidian.

The status of a job posting is synonymous with its location. The majority of job postings will be under `archived/` or `applied/`.

<img width="326" height="325" alt="Capture d’écran 2026-07-18 à 17 39 49" src="https://github.com/user-attachments/assets/ce514669-193c-4451-83de-70d2b9851650" />

Future plans have to do with further decomposition and designing a fully realized CLI.

## RAG & the knowledge base

To create a CV transformation plan, RAG is used to search a knowledge base for matching or transferable experience.

Chunking, embedding, and search are implemented in a separate [MCP project](https://github.com/evokateur/rag-knowledge-mcp); agents are configured to use it through a connector.[^claude]

[^claude]: I give Claude the same connector, as well as access to the data directory, and they go over CV transformation plans, looking for things the agent missed, discussing things the agent got wrong, and advising how prompts or the chunking strategy might be tweaked to improve the result.

## Built with

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

Configure a `rag-knowledge` MCP server (see below).

Configuration override hierarchy:

1. `src/*/config/settings.yaml` (defaults)
2. `~/.cv-joint/settings.yaml` (user dotfile)
3. `src/*/config/settings.local.yaml` (local overrides, gitignored)

<details>
<summary>Example user settings (<code>~/.cv-joint/settings.yaml</code>)</summary>

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

</details>

## Testing

```sh
make test
```

runs `uv run pytest tests/ --tb=short`

## Usage

Gradio:

```sh
cv-joint           # serve at http://localhost:7860
cv-joint open      # serve, then open the browser
```

CLI:

```sh
cv-joint analyze job-posting URL                # analyze a posting and save it
cv-joint list job-postings                      # list active postings (one URI per line)
cv-joint apply job-postings/{id} {cv-id}        # mark as applied with a CV
cv-joint transition job-postings/{id} archived  # file it into a location
cv-joint export-markdown                        # re-render all markdown
```
