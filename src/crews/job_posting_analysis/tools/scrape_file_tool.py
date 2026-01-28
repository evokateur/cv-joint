from pathlib import Path

from crewai.tools import BaseTool
from markdownify import markdownify


class ScrapeFileTool(BaseTool):
    name: str = "Scrape File"
    description: str = "Reads a local file and extracts content. Converts HTML to markdown for cleaner output."

    def _run(self, file_path: str) -> str:
        path = Path(file_path).expanduser()
        content = path.read_text()

        if path.suffix.lower() in (".html", ".htm"):
            content = markdownify(content)

        return content
