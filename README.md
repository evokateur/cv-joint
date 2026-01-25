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
│   ├── crews # CrewAI crews
│   │   ├── cv_analysis
│   │   └── job_posting_analysis
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
uv sync --extra dev # for tests, etc
```

Configure environment variables:

```sh
cp sample.env .env # Edit .env and add API keys
```

Configure a [knowledge base MCP server](https://github.com/evokateur/rag-knowledge-mcp) in `src/config/settings.local.yaml`, e.g.:

```yaml
# overrides settings in src/config/settings.yaml

chat: # optional
  model: "gpt-4o-mini" # default
  temperature: 0.7 # default

mcp:
  rag-knowledge:
    command: "/Users/footpad/.local/bin/uv"
    args:
      - "run"
      - "--directory"
      - "/Users/footpad/code/rag-knowledge-mcp"
      - "python"
      - "rag_knowledge_mcp.py"
    tool_name: "rag_search_knowledge" # required for LLM context
    env:
      LOG_LEVEL: "INFO"
```

## Usage

```sh
uv run joint
```

A browser window should open at [`http://localhost:7860`](http://localhost:7860)
