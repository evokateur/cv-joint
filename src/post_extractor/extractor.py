from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from markdownify import markdownify


_DEVALUE_SPECIAL_TAGS = frozenset({
    "Reactive", "Set", "Map", "Date", "RegExp", "Error",
    "URL", "BigInt", "undefined", "NaN", "Infinity", "-Infinity", "-0",
})

_WRONG_FILE_ERROR = """\
Could not find the expected Upwork job data in this HTML file.
"""
_GENERIC_EXTRACTION_ERROR = "Could not find recognizable job posting content in this HTML file."
_NOT_HTML_ERROR = "Input file does not contain HTML."
_UPWORK_BASE_URL = "https://www.upwork.com"
_WELCOME_TO_THE_JUNGLE_HOSTS = frozenset({
    "app.welcometothejungle.com",
    "welcometothejungle.com",
})
_WELCOME_TO_THE_JUNGLE_EXPERIENCE_LEVELS = (
    ("Junior", re.compile(r"\bJunior\b", re.IGNORECASE)),
    ("Mid", re.compile(r"\bMid\b", re.IGNORECASE)),
    ("Senior", re.compile(r"\bSenior\b", re.IGNORECASE)),
    ("Expert", re.compile(r"\bExpert\b", re.IGNORECASE)),
)
_WELCOME_TO_THE_JUNGLE_TESTIDS = (
    "job-technology-used",
    "company-sector-tags",
    "experience-section",
    "job-locations",
    "salary-section",
)
_CONTENT_KEYWORDS = (
    "job description",
    "about the role",
    "about this role",
    "responsibilities",
    "requirements",
    "qualifications",
    "what you'll do",
    "what you will do",
    "about you",
)
_JUNK_TAGS = ("script", "style", "nav", "footer", "noscript", "svg", "form")
_JUNK_CLASS_PATTERNS = (
    "cookie",
    "consent",
    "newsletter",
    "share",
    "social",
    "banner",
    "header",
    "footer",
    "menu",
    "modal",
)
_ATTACHMENT_PATTERNS = (".pdf", ".doc", ".docx", ".rtf", "attachment", "download")


class ExtractorMismatchError(ValueError):
    pass


class _DataTestIdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._stack: list[dict[str, Any]] = []
        self.results: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        self._stack.append(
            {
                "tag": tag,
                "testid": attrs_dict.get("data-testid"),
                "parts": [],
            }
        )

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return

        frame = self._stack.pop()
        if frame["tag"] != tag:
            return

        testid = frame["testid"]
        if not testid:
            return

        value = _normalize_whitespace("".join(frame["parts"]))
        if not value:
            return

        values = self.results.setdefault(testid, [])
        if value not in values:
            values.append(value)

        for parent in reversed(self._stack):
            if not parent["testid"]:
                continue
            if parent["parts"] and not parent["parts"][-1].endswith((", ", " ", "\n", "\t")):
                parent["parts"].append(", ")
            parent["parts"].append(value)

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return

        for frame in reversed(self._stack):
            if not frame["testid"]:
                continue
            frame["parts"].append(data)
            break


class _ChildTextExtractor(HTMLParser):
    def __init__(self, container_testid: str):
        super().__init__()
        self._container_testid = container_testid
        self._container_depth = 0
        self._child_depth = 0
        self._child_parts: list[str] = []
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if attrs_dict.get("data-testid") == self._container_testid:
            self._container_depth += 1
            return

        if self._container_depth == 1:
            self._child_depth = 1
            self._child_parts = []
            return

        if self._child_depth > 0:
            self._child_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._child_depth > 0:
            self._child_depth -= 1
            if self._child_depth == 0:
                value = _normalize_whitespace("".join(self._child_parts))
                if value and value not in self.values:
                    self.values.append(value)
            return

        if self._container_depth > 0:
            self._container_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._child_depth > 0:
            self._child_parts.append(data)


class _FlatTextExtractor(HTMLParser):
    def __init__(self, container_testid: str):
        super().__init__()
        self._container_testid = container_testid
        self._capture_depth = 0
        self._parts: list[str] = []
        self.value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if attrs_dict.get("data-testid") == self._container_testid:
            self._capture_depth = 1
            return

        if self._capture_depth > 0:
            self._capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth == 0:
            return

        self._capture_depth -= 1
        if self._capture_depth == 0:
            self.value = _normalize_whitespace(" ".join(self._parts))

    def handle_data(self, data: str) -> None:
        if self._capture_depth == 0:
            return

        value = data.strip()
        if value:
            self._parts.append(value)


def _contains_upwork_job_payload(flat_data: Any) -> bool:
    if not isinstance(flat_data, list):
        return False

    try:
        root = _revive_devalue(flat_data)
        return bool(root["vuex"]["jobDetails"]["job"]["uid"])
    except (KeyError, TypeError, IndexError):
        return False


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_tags(value: str) -> str:
    return _normalize_whitespace(re.sub(r"<[^>]+>", " ", value))


def _dedupe_repeated_phrase(value: str) -> str:
    normalized = _normalize_whitespace(value)
    words = normalized.split()
    if len(words) % 2 == 0:
        midpoint = len(words) // 2
        if words[:midpoint] == words[midpoint:]:
            return " ".join(words[:midpoint])
    return normalized


def _contains_html(content: str) -> bool:
    return bool(re.search(r"<[a-zA-Z][^>]*>", content))


def _render_markdown(html: str) -> str:
    content = html.strip()
    if not content:
        return ""
    if "<" not in content or ">" not in content:
        return content
    markdown = markdownify(
        content,
        heading_style="ATX",
        bullets="-",
        strong_em_symbol="*",
    )
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _extract_json_ld_blocks(html: str) -> list[Any]:
    blocks = []
    pattern = re.compile(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        raw_json = match.group(1).strip()
        if '"JobPosting"' not in raw_json:
            continue

        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, list):
            blocks.extend(item for item in parsed if isinstance(item, dict))
            continue

        if isinstance(parsed, dict):
            blocks.append(parsed)

    return blocks


def _resolve_relative_links(html: str, source_url: str | None) -> str:
    if not source_url:
        return html

    def replace(match: re.Match[str]) -> str:
        attr_name = match.group(1)
        quote = match.group(2)
        raw_value = match.group(3)
        resolved = urljoin(source_url, raw_value)
        return f'{attr_name}={quote}{resolved}{quote}'

    return re.sub(r'(href|src)=(["\'])(.*?)\2', replace, html, flags=re.IGNORECASE)


def _extract_tag_content(html: str, tag_name: str) -> list[str]:
    pattern = re.compile(
        rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>",
        re.IGNORECASE | re.DOTALL,
    )
    return [match.group(1).strip() for match in pattern.finditer(html)]


def _extract_tag_blocks(html: str, tag_name: str) -> list[str]:
    pattern = re.compile(
        rf"<{tag_name}\b[^>]*>.*?</{tag_name}>",
        re.IGNORECASE | re.DOTALL,
    )
    return [match.group(0).strip() for match in pattern.finditer(html)]


def _remove_junk_blocks(html: str) -> str:
    cleaned = html
    for tag_name in _JUNK_TAGS:
        cleaned = re.sub(
            rf"<{tag_name}\b[^>]*>.*?</{tag_name}>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

    class_pattern = "|".join(re.escape(pattern) for pattern in _JUNK_CLASS_PATTERNS)
    cleaned = re.sub(
        rf"<(?P<tag>\w+)\b[^>]*(?:class|id)=['\"][^'\"]*(?:{class_pattern})[^'\"]*['\"][^>]*>.*?</(?P=tag)>",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return cleaned


def _extract_title_from_html(html: str) -> str:
    for candidate in _extract_tag_content(html, "h1"):
        text = _strip_tags(candidate)
        if text:
            return text

    title_matches = _extract_tag_content(html, "title")
    if title_matches:
        return _strip_tags(title_matches[0])

    return ""


def _extract_heading_texts(html: str, tag_name: str) -> list[str]:
    headings = []
    for candidate in _extract_tag_content(html, tag_name):
        text = _strip_tags(candidate)
        if text:
            headings.append(text)
    return headings


def _score_candidate_block(block_html: str) -> int:
    text = _strip_tags(block_html)
    if not text:
        return 0

    text_lower = text.lower()
    score = len(text)
    if any(keyword in text_lower for keyword in _CONTENT_KEYWORDS):
        score += 1000
    if "<h1" in block_html.lower():
        score += 500
    if "<h2" in block_html.lower():
        score += 250
    return score


def _extract_description_block(html: str) -> str:
    candidates: list[str] = []
    for tag_name in ("main", "article"):
        candidates.extend(_extract_tag_blocks(html, tag_name))

    role_pattern = re.compile(
        r"<(?P<tag>\w+)\b[^>]*role=['\"]main['\"][^>]*>.*?</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    candidates.extend(match.group(0).strip() for match in role_pattern.finditer(html))

    section_pattern = re.compile(
        r"<(?P<tag>section|div)\b[^>]*>.*?</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in section_pattern.finditer(html):
        block_html = match.group(0).strip()
        block_text = _strip_tags(block_html).lower()
        if any(keyword in block_text for keyword in _CONTENT_KEYWORDS):
            candidates.append(block_html)

    candidates.append(html)

    best_block = ""
    best_score = 0
    for candidate in candidates:
        cleaned = _remove_junk_blocks(candidate)
        score = _score_candidate_block(cleaned)
        if score > best_score:
            best_block = cleaned
            best_score = score

    return best_block.strip()


def _extract_links(html: str, source_url: str | None) -> list["Attachment"]:
    links: list[Attachment] = []
    link_pattern = re.compile(
        r"<a\b[^>]*href=['\"](.*?)['\"][^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in link_pattern.finditer(html):
        href = match.group(1).strip()
        label = _strip_tags(match.group(2))
        if not href:
            continue

        resolved_href = urljoin(source_url, href) if source_url else href
        href_text = f"{resolved_href} {label}".lower()
        if not any(pattern in href_text for pattern in _ATTACHMENT_PATTERNS):
            continue

        file_name = label or Path(resolved_href).name or resolved_href
        links.append(Attachment(file_name=file_name, url=resolved_href))

    return links


def _extract_data_testid_values(html: str) -> dict[str, list[str]]:
    parser = _DataTestIdParser()
    parser.feed(html)
    parser.close()
    return parser.results


def _extract_child_texts_from_testid_container(html: str, container_testid: str) -> list[str]:
    parser = _ChildTextExtractor(container_testid)
    parser.feed(html)
    parser.close()
    return parser.values


def _extract_flat_text_from_testid_container(html: str, container_testid: str) -> str:
    parser = _FlatTextExtractor(container_testid)
    parser.feed(html)
    parser.close()
    return _dedupe_repeated_phrase(parser.value)


def _extract_data_test_content(html: str, data_test: str) -> str:
    pattern = re.compile(
        rf'<(?P<tag>\w+)\b[^>]*data-test=["\']{re.escape(data_test)}["\'][^>]*>(.*?)</(?P=tag)>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return ""
    return match.group(2).strip()


def _revive_devalue(data: list[Any]) -> Any:
    cache: dict[int, Any] = {}

    def resolve(index: int) -> Any:
        if index in cache:
            return cache[index]

        item = data[index]

        if isinstance(item, dict):
            result: dict[str, Any] = {}
            cache[index] = result
            for key, value in item.items():
                result[key] = resolve(value)
            return result

        if isinstance(item, list):
            if item and isinstance(item[0], str) and item[0] in _DEVALUE_SPECIAL_TAGS:
                tag = item[0]
                if tag == "Reactive":
                    resolved = resolve(item[1])
                    cache[index] = resolved
                    return resolved
                if tag == "Date":
                    cache[index] = item[1]
                    return item[1]
                cache[index] = None
                return None

            result_list: list[Any] = []
            cache[index] = result_list
            for value in item:
                result_list.append(resolve(value))
            return result_list

        cache[index] = item
        return item

    header = data[0]
    root_index = header[1] if isinstance(header, list) and header[0] == "Reactive" else 1
    return resolve(root_index)


@dataclass
class Attachment:
    file_name: str
    url: str


@dataclass
class JobPosting:
    title: str
    description_html: str
    attachments: list[Attachment]
    company: str = ""
    salary: str = ""
    experience: str = ""
    category: str = ""
    category_group: str = ""
    project_types: list[str] | None = None
    workload: str = ""
    engagement_duration: str = ""
    contractor_tier: str = ""
    locations: list[str] | None = None
    countries: list[str] | None = None
    regions: list[str] | None = None
    states: list[str] | None = None
    timezones: list[str] | None = None
    languages: list[str] | None = None
    screening_questions: list[str] | None = None
    location_requirement: str = ""
    portfolio_requirement: str = ""
    rising_talent_preference: str = ""
    job_success_score: str = ""
    odesk_hours: str = ""
    technologies: list[str] | None = None
    company_sector_tags: list[str] | None = None
    skills_and_expertise: list[str] | None = None
    data_testid_values: dict[str, list[str]] | None = None

    def to_markdown(self) -> str:
        body = _render_markdown(self.description_html)
        skills_and_expertise = self._render_skills_and_expertise()
        screening_questions = self._render_screening_questions()
        attachments = self._render_attachments()
        metadata = self._render_metadata()
        if self.title and body:
            return f"# {self.title}\n\n{metadata}{body}{skills_and_expertise}{screening_questions}{attachments}"
        if self.title:
            if not metadata:
                return f"# {self.title}{skills_and_expertise}{screening_questions}{attachments}"
            return f"# {self.title}\n\n{metadata.rstrip()}{skills_and_expertise}{screening_questions}{attachments}"
        if self.company and body:
            return f"{metadata}{body}{skills_and_expertise}{screening_questions}{attachments}"
        if metadata:
            return f"{metadata.rstrip()}{skills_and_expertise}{screening_questions}{attachments}"
        if body:
            return f"{body}{skills_and_expertise}{screening_questions}{attachments}"
        if skills_and_expertise:
            return f"{skills_and_expertise.lstrip()}{screening_questions}{attachments}"
        if screening_questions:
            return f"{screening_questions.lstrip()}{attachments}"
        return attachments.lstrip("\n") if attachments else ""

    def _render_metadata(self) -> str:
        lines = []
        if self.company:
            lines.append(f"- **Company:** {self.company}")
        if self.salary:
            lines.append(f"- **Salary:** {self.salary}")
        if self.experience:
            lines.append(f"- **Experience:** {self.experience}")
        if self.category:
            lines.append(f"- **Category:** {self.category}")
        if self.category_group:
            lines.append(f"- **Category Group:** {self.category_group}")
        if self.project_types:
            lines.append(f"- **Project Types:** {', '.join(self.project_types)}")
        if self.workload:
            lines.append(f"- **Workload:** {self.workload}")
        if self.engagement_duration:
            lines.append(f"- **Engagement Duration:** {self.engagement_duration}")
        if self.contractor_tier:
            lines.append(f"- **Contractor Tier:** {self.contractor_tier}")
        if self.locations:
            lines.append(f"- **Locations:** {', '.join(self.locations)}")
        if self.countries:
            lines.append(f"- **Countries:** {', '.join(self.countries)}")
        if self.regions:
            lines.append(f"- **Regions:** {', '.join(self.regions)}")
        if self.states:
            lines.append(f"- **States:** {', '.join(self.states)}")
        if self.timezones:
            lines.append(f"- **Timezones:** {', '.join(self.timezones)}")
        if self.languages:
            lines.append(f"- **Languages:** {', '.join(self.languages)}")
        if self.location_requirement:
            lines.append(f"- **Location Requirement:** {self.location_requirement}")
        if self.portfolio_requirement:
            lines.append(f"- **Portfolio Requirement:** {self.portfolio_requirement}")
        if self.rising_talent_preference:
            lines.append(f"- **Rising Talent Preference:** {self.rising_talent_preference}")
        if self.job_success_score:
            lines.append(f"- **Minimum Job Success Score:** {self.job_success_score}")
        if self.odesk_hours:
            lines.append(f"- **Minimum Odesk Hours:** {self.odesk_hours}")
        if self.technologies:
            lines.append(f"- **Technologies:** {', '.join(self.technologies)}")
        if self.company_sector_tags:
            lines.append(f"- **Sectors:** {', '.join(self.company_sector_tags)}")
        if not lines:
            return ""
        return "\n".join(lines) + "\n\n"

    def _render_attachments(self) -> str:
        if not self.attachments:
            return "\n"

        lines = ["", "", "## Attachments", ""]
        for attachment in self.attachments:
            lines.append(f"- [{attachment.file_name}]({attachment.url})")
        return "\n".join(lines) + "\n"

    def _render_skills_and_expertise(self) -> str:
        if not self.skills_and_expertise:
            return ""

        lines = ["", "", "## Skills and Expertise", ""]
        for skill in self.skills_and_expertise:
            lines.append(f"- {skill}")
        return "\n".join(lines) + "\n"

    def _render_screening_questions(self) -> str:
        if not self.screening_questions:
            return ""

        lines = ["", "", "## Screening Questions", ""]
        for question in self.screening_questions:
            lines.append(f"- {question}")
        return "\n".join(lines) + "\n"


ExtractedJob = JobPosting


class UpworkExtractor:
    _PAYLOAD_RE = re.compile(
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        re.DOTALL,
    )
    _NUXT_WORKLOAD_RE = re.compile(
        r'data-test=["\']job-metrics-workload["\'][^>]*>.*?<span[^>]*label-medium[^>]*>(.*?)</span>.*?<span[^>]*body-small[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    _NUXT_DURATION_RE = re.compile(
        r'data-test=["\']job-metrics-duration["\'][^>]*>.*?<span[^>]*label-medium[^>]*>(.*?)</span>.*?<span[^>]*body-small[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    _NUXT_EXPERIENCE_RE = re.compile(
        r'data-test=["\']job-metrics-experience["\'][^>]*>.*?<span[^>]*label-medium[^>]*>(.*?)</span>.*?<span[^>]*body-small[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, html: str):
        self._html = html
        self._state: dict[str, Any] | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "UpworkExtractor":
        return cls(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_string(cls, html: str, source_url: str | None = None) -> "UpworkExtractor":
        return cls(html)

    @classmethod
    def matches(cls, html: str, source_url: str | None = None) -> bool:
        if not _contains_html(html):
            return False

        for raw_json in cls._PAYLOAD_RE.findall(html):
            try:
                flat = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            if _contains_upwork_job_payload(flat):
                return True

        return cls._matches_nuxt_job_page(html)

    @classmethod
    def _matches_nuxt_job_page(cls, html: str) -> bool:
        return all(
            marker in html
            for marker in (
                'id="__NUXT_DATA__"',
                'data-test="job-title"',
                'data-test="job-description-content"',
            )
        )

    def _get_state(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state

        if not _contains_html(self._html):
            raise ValueError(_NOT_HTML_ERROR)

        for raw_json in self._PAYLOAD_RE.findall(self._html):
            try:
                flat = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            if not _contains_upwork_job_payload(flat):
                continue

            self._state = _revive_devalue(flat)
            return self._state

        raise ExtractorMismatchError(_WRONG_FILE_ERROR)

    def extract(self) -> JobPosting:
        try:
            return self.extract_or_raise_mismatch()
        except ExtractorMismatchError as error:
            raise ValueError(str(error)) from error

    def extract_or_raise_mismatch(self) -> JobPosting:
        try:
            job_details = self._get_job_details()
        except ExtractorMismatchError:
            if self._matches_nuxt_job_page(self._html):
                return self._extract_nuxt_job_posting()
            raise

        job = self._get_job(job_details)
        return JobPosting(
            title=self._extract_title(job),
            description_html=self._extract_description(job),
            attachments=self._extract_attachments(job),
            category=self._extract_named_value(job.get("category")),
            category_group=self._extract_named_value(job.get("categoryGroup")),
            project_types=self._extract_project_types(job),
            workload=self._extract_string(job.get("workload")),
            engagement_duration=self._extract_engagement_duration(job),
            contractor_tier=self._extract_contractor_tier(job),
            countries=self._extract_qualification_list(job, "countries"),
            regions=self._extract_qualification_list(job, "regions"),
            states=self._extract_qualification_list(job, "states"),
            timezones=self._extract_qualification_list(job, "timezones"),
            languages=self._extract_qualification_list(job, "languages"),
            screening_questions=self._extract_screening_questions(job),
            location_requirement=self._extract_location_requirement(job),
            portfolio_requirement=self._extract_boolean_requirement(
                job,
                field_name="shouldHavePortfolio",
                true_value="Required",
                false_value="Not required",
            ),
            rising_talent_preference=self._extract_boolean_requirement(
                job,
                field_name="risingTalent",
                true_value="Preferred",
                false_value="Not required",
            ),
            job_success_score=self._extract_numeric_requirement(job, "minJobSuccessScore", suffix="%"),
            odesk_hours=self._extract_numeric_requirement(job, "minOdeskHours", suffix=" hours"),
            skills_and_expertise=self._extract_skills_and_expertise(job_details),
        )

    def _extract_nuxt_job_posting(self) -> JobPosting:
        description_html = _extract_data_test_content(self._html, "job-description-content")
        return JobPosting(
            title=self._extract_nuxt_title(),
            description_html=description_html,
            attachments=[],
            category=self._extract_nuxt_category(),
            project_types=self._extract_nuxt_project_types(),
            workload=self._extract_nuxt_metric(self._NUXT_WORKLOAD_RE, skip_value="Hourly"),
            engagement_duration=self._extract_nuxt_metric(self._NUXT_DURATION_RE, skip_value="Duration"),
            experience=self._extract_nuxt_metric(self._NUXT_EXPERIENCE_RE),
            countries=self._extract_nuxt_countries(),
            screening_questions=self._extract_nuxt_questions(),
            rising_talent_preference=self._extract_nuxt_rising_talent_preference(),
            job_success_score=self._extract_nuxt_job_success_score(),
            skills_and_expertise=self._extract_nuxt_skills(),
        )

    def _extract_nuxt_title(self) -> str:
        return _strip_tags(_extract_data_test_content(self._html, "job-title"))

    def _extract_nuxt_category(self) -> str:
        category_html = _extract_data_test_content(self._html, "category")
        category_text = _strip_tags(category_html)
        if category_text.startswith("current page "):
            return category_text.removeprefix("current page ").strip()
        return category_text

    def _extract_nuxt_metric(self, pattern: re.Pattern[str], skip_value: str = "") -> str:
        match = pattern.search(self._html)
        if not match:
            return ""

        values = []
        for raw_value in match.groups():
            normalized_value = _strip_tags(raw_value)
            if not normalized_value or normalized_value == skip_value:
                continue
            values.append(normalized_value)

        return " ".join(values).strip()

    def _extract_nuxt_project_types(self) -> list[str]:
        segmentations_html = _extract_data_test_content(self._html, "segmentations")
        match = re.search(
            r'Project Type:</span>\s*<span[^>]*>(.*?)</span>',
            segmentations_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []
        project_type = _strip_tags(match.group(1))
        return [project_type] if project_type else []

    def _extract_nuxt_questions(self) -> list[str]:
        questions_html = _extract_data_test_content(self._html, "questions-list")
        if not questions_html:
            return []

        questions = []
        for match in re.finditer(
            r'<li\b[^>]*data-test=["\']question-item["\'][^>]*>(.*?)</li>',
            questions_html,
            re.IGNORECASE | re.DOTALL,
        ):
            question = _strip_tags(match.group(1))
            if question:
                questions.append(question)
        return self._dedupe_values(questions)

    def _extract_nuxt_skills(self) -> list[str]:
        skills = []
        for match in re.finditer(
            r'<(?:a|span)\b[^>]*class=["\'][^"\']*skill-tag-host[^"\']*["\'][^>]*>(.*?)</(?:a|span)>',
            self._html,
            re.IGNORECASE | re.DOTALL,
        ):
            skill = _strip_tags(match.group(1))
            if skill:
                skills.append(skill)
        return self._dedupe_values(skills)

    def _extract_nuxt_countries(self) -> list[str]:
        match = re.search(
            r'data-test=["\']location-label["\'][^>]*>.*?<span\b[^>]*tabindex=["\']0["\'][^>]*>(.*?)</span>',
            self._html,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []

        country = _strip_tags(match.group(1))
        return [country] if country else []

    def _extract_nuxt_rising_talent_preference(self) -> str:
        qualification_text = _strip_tags(_extract_data_test_content(self._html, "qualification-rising-talent"))
        if qualification_text.endswith("Yes"):
            return "Preferred"
        if qualification_text.endswith("No"):
            return "Not required"
        return ""

    def _extract_nuxt_job_success_score(self) -> str:
        qualification_text = _strip_tags(_extract_data_test_content(self._html, "qualification-job-success-score"))
        match = re.search(r'(\d+%)', qualification_text)
        if not match:
            return ""
        return match.group(1)

    def _get_job_details(self) -> dict[str, Any]:
        return self._get_state()["vuex"]["jobDetails"]

    def _get_job(self, job_details: dict[str, Any]) -> dict[str, Any]:
        return job_details["job"]

    def _extract_title(self, job: dict[str, Any]) -> str:
        title = job.get("title")
        if not isinstance(title, str):
            return ""
        return title.strip()

    def _extract_description(self, job: dict[str, Any]) -> str:
        for field_name in ("descriptionHtml", "description", "legacyCiphertextDescription"):
            value = self._extract_string(job.get(field_name))
            if value:
                return value
        return ""

    def _extract_attachments(self, job: dict[str, Any]) -> list[Attachment]:
        attachments = job.get("attachments")
        if not isinstance(attachments, list):
            return []

        extracted_attachments = []
        for attachment in attachments:
            extracted_attachment = self._extract_attachment(attachment)
            if extracted_attachment is not None:
                extracted_attachments.append(extracted_attachment)
        return extracted_attachments

    def _extract_attachment(self, attachment: Any) -> Attachment | None:
        if not isinstance(attachment, dict):
            return None

        file_name = self._extract_string(attachment.get("fileName"))
        uri = attachment.get("uri")
        if not file_name:
            return None
        if not isinstance(uri, str) or not uri.startswith("/"):
            return None

        return Attachment(
            file_name=file_name,
            url=f"{_UPWORK_BASE_URL}{uri}",
        )

    def _extract_skills_and_expertise(self, job_details: dict[str, Any]) -> list[str]:
        skills_payload = self._get_skills_payload(job_details)
        if not skills_payload:
            return []

        skills = []
        skills.extend(self._extract_occupation_skills(skills_payload))
        skills.extend(self._extract_ontology_skills(skills_payload))
        skills.extend(self._extract_additional_skills(skills_payload))
        return self._dedupe_values(skills)

    def _get_skills_payload(self, job_details: dict[str, Any]) -> dict[str, Any]:
        sands = job_details.get("sands")
        if not isinstance(sands, dict):
            return {}
        return sands

    def _extract_occupation_skills(self, skills_payload: dict[str, Any]) -> list[str]:
        occupation = skills_payload.get("occupation")
        if not isinstance(occupation, dict):
            return []

        pref_label = self._extract_string(occupation.get("prefLabel"))
        return [pref_label] if pref_label else []

    def _extract_ontology_skills(self, skills_payload: dict[str, Any]) -> list[str]:
        ontology_skills = skills_payload.get("ontologySkills")
        if not isinstance(ontology_skills, list):
            return []

        skill_names = []
        for group in ontology_skills:
            if not isinstance(group, dict):
                continue
            skill_names.extend(self._extract_skill_names(group.get("children")))
        return skill_names

    def _extract_additional_skills(self, skills_payload: dict[str, Any]) -> list[str]:
        return self._extract_skill_names(skills_payload.get("additionalSkills"))

    def _extract_named_value(self, value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        return self._extract_string(value.get("name"))

    def _extract_project_types(self, job: dict[str, Any]) -> list[str]:
        segmentation_data = job.get("segmentationData")
        if not isinstance(segmentation_data, list):
            return []

        project_types = []
        for item in segmentation_data:
            if not isinstance(item, dict):
                continue

            label = self._extract_string(item.get("label"))
            if label:
                project_types.append(label)

        return self._dedupe_values(project_types)

    def _extract_engagement_duration(self, job: dict[str, Any]) -> str:
        engagement_duration = job.get("engagementDuration")
        if not isinstance(engagement_duration, dict):
            return ""

        label = self._extract_string(engagement_duration.get("label"))
        weeks = engagement_duration.get("weeks")
        if label and isinstance(weeks, int):
            return f"{label} ({weeks} weeks)"
        return label

    def _extract_contractor_tier(self, job: dict[str, Any]) -> str:
        contractor_tier = job.get("contractorTier")
        if contractor_tier is None:
            return ""
        return str(contractor_tier).strip()

    def _extract_qualification_list(self, job: dict[str, Any], field_name: str) -> list[str]:
        qualifications = job.get("qualifications")
        if not isinstance(qualifications, dict):
            return []

        values = qualifications.get(field_name)
        if not isinstance(values, list):
            return []

        extracted_values = []
        for value in values:
            normalized_value = self._extract_string(value)
            if normalized_value:
                extracted_values.append(normalized_value)

        return self._dedupe_values(extracted_values)

    def _extract_screening_questions(self, job: dict[str, Any]) -> list[str]:
        questions = job.get("questions")
        if not isinstance(questions, list):
            return []

        extracted_questions = []
        for question in questions:
            if isinstance(question, dict):
                text = self._extract_string(question.get("question"))
                if not text:
                    text = self._extract_string(question.get("text"))
            else:
                text = self._extract_string(question)

            if text:
                extracted_questions.append(text)

        return self._dedupe_values(extracted_questions)

    def _extract_location_requirement(self, job: dict[str, Any]) -> str:
        qualifications = job.get("qualifications")
        if not isinstance(qualifications, dict):
            return ""

        if qualifications.get("locationCheckRequired") is True:
            return "Required"
        if qualifications.get("locationCheckRequired") is False:
            return "Not required"
        return ""

    def _extract_boolean_requirement(
        self,
        job: dict[str, Any],
        field_name: str,
        true_value: str,
        false_value: str,
    ) -> str:
        qualifications = job.get("qualifications")
        if not isinstance(qualifications, dict):
            return ""

        value = qualifications.get(field_name)
        if value is True:
            return true_value
        if value is False:
            return false_value
        return ""

    def _extract_numeric_requirement(self, job: dict[str, Any], field_name: str, suffix: str) -> str:
        qualifications = job.get("qualifications")
        if not isinstance(qualifications, dict):
            return ""

        value = qualifications.get(field_name)
        if not isinstance(value, int | float):
            return ""
        return f"{value}{suffix}"

    def _extract_skill_names(self, skills: Any) -> list[str]:
        if not isinstance(skills, list):
            return []

        skill_names = []
        for skill in skills:
            if not isinstance(skill, dict):
                continue

            name = self._extract_string(skill.get("name"))
            if name:
                skill_names.append(name)
        return skill_names

    def _dedupe_values(self, values: list[str]) -> list[str]:
        deduped_values = []
        for value in values:
            if value not in deduped_values:
                deduped_values.append(value)
        return deduped_values

    def _extract_string(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()


class GenericHtmlExtractor:
    def __init__(self, html: str, source_url: str | None = None):
        self._html = html
        self._source_url = source_url

    @classmethod
    def from_string(cls, html: str, source_url: str | None = None) -> "GenericHtmlExtractor":
        return cls(html, source_url=source_url)

    @classmethod
    def matches(cls, html: str, source_url: str | None = None) -> bool:
        if not _contains_html(html):
            return False

        description_html = _extract_description_block(html)
        body_text = _strip_tags(description_html)
        title = _extract_title_from_html(html)
        return len(body_text) >= 80 or bool(title)

    def extract(self) -> JobPosting:
        if not _contains_html(self._html):
            raise ValueError(_NOT_HTML_ERROR)

        description_html = _extract_description_block(self._html)
        description_html = _resolve_relative_links(description_html, self._source_url)
        title = _extract_title_from_html(self._html)
        attachments = _extract_links(description_html, self._source_url)
        body_text = _strip_tags(description_html)

        if len(body_text) < 80 and not title:
            raise ValueError(_GENERIC_EXTRACTION_ERROR)

        return JobPosting(
            title=title,
            description_html=description_html,
            attachments=attachments,
        )


class WelcomeToTheJungleExtractor:
    _FIELD_EXTRACTORS = {
        "technologies": ("job-technology-used", "container_children"),
        "company_sector_tags": ("company-sector-tags", "container_children"),
        "salary": ("salary-section", "bucket_first"),
        "experience": ("experience-section", "experience_levels"),
        "locations": ("job-locations", "container_children"),
    }

    def __init__(self, html: str, source_url: str | None = None):
        self._html = html
        self._source_url = source_url
        self._job_posting: dict[str, Any] | None = None

    @classmethod
    def from_string(
        cls,
        html: str,
        source_url: str | None = None,
    ) -> "WelcomeToTheJungleExtractor":
        return cls(html, source_url=source_url)

    @classmethod
    def matches(cls, html: str, source_url: str | None = None) -> bool:
        if not _contains_html(html):
            return False

        has_job_posting = cls._find_job_posting(html) is not None
        if not has_job_posting:
            return False

        has_wttj_marker = cls._is_wttj_source(source_url) or "Welcome to the Jungle" in html
        if has_wttj_marker:
            return True

        data_testid_values = _extract_data_testid_values(html)
        return any(testid in data_testid_values for testid in _WELCOME_TO_THE_JUNGLE_TESTIDS)

    @classmethod
    def _is_wttj_source(cls, source_url: str | None) -> bool:
        if not source_url:
            return False

        host = urlparse(source_url).netloc.lower()
        return any(host == allowed_host or host.endswith(f".{allowed_host}") for allowed_host in _WELCOME_TO_THE_JUNGLE_HOSTS)

    @classmethod
    def _find_job_posting(cls, html: str) -> dict[str, Any] | None:
        for block in _extract_json_ld_blocks(html):
            if block.get("@type") != "JobPosting":
                continue
            if not isinstance(block.get("hiringOrganization"), dict):
                continue
            return block
        return None

    def extract(self) -> JobPosting:
        if not _contains_html(self._html):
            raise ValueError(_NOT_HTML_ERROR)

        job_posting = self._job_posting or self._find_job_posting(self._html)
        if job_posting is None:
            raise ValueError(_GENERIC_EXTRACTION_ERROR)

        self._job_posting = job_posting
        company = self._extract_company(job_posting)
        description_html = self._build_description_html(job_posting)
        attachments = _extract_links(description_html, self._source_url)
        data_testid_values = _extract_data_testid_values(self._html)
        normalized_fields = self._extract_structured_fields(data_testid_values)

        return JobPosting(
            title=_normalize_whitespace(str(job_posting.get("title", ""))),
            company=company,
            salary=self._coerce_string_field(normalized_fields.get("salary")),
            experience=self._coerce_string_field(normalized_fields.get("experience")),
            locations=self._coerce_list_field(normalized_fields.get("locations")),
            description_html=description_html,
            attachments=attachments,
            technologies=self._coerce_list_field(normalized_fields.get("technologies")),
            company_sector_tags=self._coerce_list_field(normalized_fields.get("company_sector_tags")),
            data_testid_values=data_testid_values,
        )

    def _extract_company(self, job_posting: dict[str, Any]) -> str:
        organization = job_posting.get("hiringOrganization")
        if not isinstance(organization, dict):
            return ""
        return _normalize_whitespace(str(organization.get("name", "")))

    def _build_description_html(self, job_posting: dict[str, Any]) -> str:
        sections = []
        description = self._clean_html_field(job_posting.get("description"))
        responsibilities = self._clean_html_field(job_posting.get("responsibilities"))
        skills = self._clean_html_field(job_posting.get("skills"))
        benefits = self._clean_html_field(job_posting.get("jobBenefits"))

        if description:
            sections.append(description)
        if responsibilities and responsibilities not in sections:
            sections.append(f"<h1>Responsibilities</h1>\n{responsibilities}")
        if skills and skills not in sections:
            sections.append(f"<h1>Skills</h1>\n{skills}")
        if benefits and benefits not in sections:
            sections.append(f"<h1>Benefits</h1>\n{benefits}")

        return "\n\n".join(section for section in sections if section).strip()

    def _clean_html_field(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""

        cleaned = value.strip()
        if not cleaned:
            return ""

        cleaned = re.sub(r"</li>\s*,\s*<li", "</li><li", cleaned)
        return cleaned.strip()

    def _extract_structured_fields(
        self,
        data_testid_values: dict[str, list[str]],
    ) -> dict[str, list[str] | str]:
        structured_fields: dict[str, list[str] | str] = {}
        for field_name, (testid, strategy) in self._FIELD_EXTRACTORS.items():
            if strategy == "container_children":
                values = _extract_child_texts_from_testid_container(self._html, testid)
                if values:
                    structured_fields[field_name] = values
                continue

            if strategy == "bucket_first":
                value = _extract_flat_text_from_testid_container(self._html, testid)
                if value:
                    structured_fields[field_name] = value
                    continue

                values = data_testid_values.get(testid, [])
                if values:
                    structured_fields[field_name] = values[0]
                continue

            if strategy == "experience_levels":
                value = _extract_flat_text_from_testid_container(self._html, testid)
                if value:
                    levels = self._extract_experience_levels(value)
                    if levels:
                        structured_fields[field_name] = ", ".join(levels)
                        continue
                    structured_fields[field_name] = value

        return structured_fields

    def _coerce_list_field(self, value: list[str] | str | None) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value:
            return [value]
        return []

    def _coerce_string_field(self, value: list[str] | str | None) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            return value[0]
        return ""

    def _extract_experience_levels(self, value: str) -> list[str]:
        levels = []
        for label, pattern in _WELCOME_TO_THE_JUNGLE_EXPERIENCE_LEVELS:
            if pattern.search(value):
                levels.append(label)
        return levels


def select_extractor(html: str, source_url: str | None = None) -> type[Any]:
    if not _contains_html(html):
        raise ValueError(_NOT_HTML_ERROR)

    extractors = (UpworkExtractor, WelcomeToTheJungleExtractor, GenericHtmlExtractor)
    for extractor in extractors:
        if extractor.matches(html, source_url=source_url):
            return extractor

    raise ValueError(_GENERIC_EXTRACTION_ERROR)


def extract_job_posting(html: str, source_url: str | None = None) -> JobPosting:
    extractor = select_extractor(html, source_url=source_url)
    return extractor.from_string(html, source_url=source_url).extract()
