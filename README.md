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
make setup # or..
make setup-dev # for tests, etc
```

Set environment variables:

```sh
cp sample.env .env # edit .env and add API keys
```

Extend/override settings by creating `~/.cv-joint/settings.yaml`   
and configuring an MCP server (other examples shown are defaults):

```yaml
chat:
  model: "gpt-4o"

mcpServers: # not in default settings
  rag-knowledge:
    command: "/absolute/path/to/uv"
    args:
      - "run"
      - "--directory"
      - "/absolute/path/to/mcp-server-project"
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
