# CV Agency

Track job postings, create targeted CV data, render CVs with LaTeX

## Features

- Create structured Job Postings from URLs
- Create structured CV data from text files
- Chat with RAG knowledge base integration
- Create optimized CV data for a job posting (in progress)
- Render CV data in LaTeX PDF files (in progress)

## Implementation

- Analysis and structured output by CrewAI crews

- Pydantic for defining job postings, CVs, and structured outputs.

- Gradio tabbed UI

- PDF CVs are rendered with Jinja2 using custom delimiters that play well with LaTeX:

  |              | customized | standard jinja2 |
  | ------------ | ---------- | --------------- |
  | Statements   | `(# #)`    | `{% %}`         |
  | Expressions  | `(( ))`    | `{{ }}`         |
  | Comments     | `%( )%`    | `{# #}`         |
  | Line Comment | `%%`       | `##`            |

Simplified project structure:

```sh
.
├── collections # persisted entities
├── output # LaTeX PDF output
├── src
│   ├── builder # LaTeX PDF rendering
│   ├── cv_analyzer # CrewAI crew
│   ├── job_posting_analyzer # CrewAI crew
│   ├── models
│   ├── repositories
│   ├── services
│   │   └── analyzers # facades for CrewAI crews
│   └── ui # Gradio app
├── templates
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

Configure [knowledge base MCP server](https://github.com/evokateur/rag-knowledge-mcp) in `src/config/settings.local.yaml`, e.g.:

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
uv run cv-agency
```

A browser window should open to `http://localhost:7860`.
