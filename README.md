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
make setup # or..
make dev-setup # for tests, etc
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

Example user settings, unnecessary defaults except where noted:

```yaml
chat:
  model: "gpt-4o"

mcpServers:
  rag-knowledge: # null in default settings
    command: "/absolute/path/to/uv"
    args:
      - "run"
      - "--directory"
      - "/absolute/path/to/mcp-server-project"
      - "python"
      - "rag_knowledge_mcp.py"
    env:
      LOG_LEVEL: "INFO"
    x-tool-name: "rag_search_knowledge" # search tool to call

crews:
  cv_analysis:
    agents:
      cv_analyst:
        model: "gpt-4o"

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

To see all merged configuration: `uv run joint --show-config`

## Usage

```sh
uv run joint
```

A browser window should open at [`http://localhost:7860`](http://localhost:7860)
