# CV Joint

Track job postings, create targeted CVs, render them with LaTeX, achieve constant velocity.

## Features

- Create structured data from Job Posting URLs
- Create structured CV data from text files
- RAG knowledge base equipped chat
- Optimize CV data for job postings (in progress)
- Create PDFs from CV data with LaTeX (in progress)

## Implementation

- Analysis and structured output with CrewAI

- Pydantic for defining domain objects and structured outputs

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
│   ├── builder # LaTeX PDF rendering
│   ├── config
│   ├── crews
│   │   ├── cv_analysis
│   │   ├── cv_optimization
│   │   └── job_posting_analysis
│   ├── infrastructure
│   ├── models
│   ├── repositories
│   │   └── filesystem.py
│   ├── services
│   │   └── analyzers # crew facades
│   │   └── application.py
│   └── ui
│   │   └── app.py # Gradio
│   │   └── cli.py
└── templates
    ├── cover-letter.tex
    └── cv.tex
```

## Setup

Initial setup:

```sh
uv sync # or..
uv sync --extra dev # for tests, etc.
```

`PHONY` make targets are also available:

```sh
make setup # runs 'uv sync'
make dev-setup  # runs 'uv sync --extra dev'
```

Set environment variables:

```sh
cp sample.env .env # edit .env and add API keys
```

Configure the `rag-knowledge` MCP server for RAG functions (see below).

Configuration override hierarchy:

1. `src/*/config/settings.yaml` (defaults)
2. `~/.cv-joint/settings.yaml` (user config, suitable for dotfiles)
3. `src/*/config/settings.local.yaml` (machine-specific overrides, gitignored)

Strings beginning with `~/` will undergo tilde expansion.

Example user settings, unnecessary defaults except where noted:

```yaml
chat:
  model: "gpt-4o"
  temperature: 0.7

mcpServers:
  rag-knowledge: # null in default settings
    command: "~/.local/bin/uv" #
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
        model: "gpt-4o"
        temperature: 0.7

repositories:
  filesystem:
    data_dir: "./data"
```

Data directory structure:

```
data/
├── collections/
│   ├── job-postings.json
│   └── cvs.json
├── job-postings/{identifier}/job-posting.json
└── cvs/{identifier}/cv.json
```

To see all merged, tilde expanded configuration:

```sh
uv run joint --show-config
```

## Testing

Run all tests (with short tracebacks):

```sh
uv run pytest /tests --tb=short # or..
make test
```

## Usage

```sh
uv run joint
```

A browser window should open at [`http://localhost:7860`](http://localhost:7860)
