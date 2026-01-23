# CV Agency

Track job postings, create targeted CV data, render CVs with LaTeX

## Features

- Creates structured Job Postings from URLs
- Creates structured CV data from text files
- Creates optimized CV data for a job posting
- Renders CV data in LaTeX PDF files

## Implementation

- Analysis and structured output by CrewAI crews

- Pydantic for defining job postings, CVs, and structured outputs.

- Gradio tabbed UI

- CVs are made with Jinja2 using custom delimiters that play well with LaTeX:

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

## Usage

```sh
uv run cv-agency
```

A browser window should open to `http://localhost:7860`.
