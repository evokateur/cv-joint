"""Resolve logical document addresses to repository records."""

from repositories.filesystem import FileSystemRepository, Record


def parse_uri(uri: str) -> dict[str, str]:
    parts = uri.strip("/").split("/")
    if parts[0] == "job-postings" and len(parts) == 2:
        return {"collection": "job-postings", "identifier": parts[1]}
    if parts[0] == "cvs" and len(parts) == 2:
        return {"collection": "cvs", "identifier": parts[1]}
    if parts[0] == "cover-letters" and len(parts) == 2:
        return {"collection": "cover-letters", "identifier": parts[1]}
    if parts[0] == "job-postings" and len(parts) == 4 and parts[2] == "cvs":
        return {
            "collection": "optimized-cvs",
            "job_posting_identifier": parts[1],
            "identifier": parts[3],
        }
    raise ValueError(f"Unrecognised URI: {uri}")


def resolve_record(repository: FileSystemRepository, uri: str) -> Record:
    """Return the governing record for a URI. Raises ValueError if not found."""
    parsed = parse_uri(uri)
    collection = parsed["collection"]

    if collection == "job-postings":
        record = repository.get_job_posting_record(parsed["identifier"])
        if record is None:
            raise ValueError(f"Not found: {uri}")
        return record

    if collection == "cvs":
        record = repository.get_cv_record(parsed["identifier"])
        if record is None:
            raise ValueError(f"Not found: {uri}")
        return record

    if collection == "cover-letters":
        record = repository.get_cover_letter_record(parsed["identifier"])
        if record is None:
            raise ValueError(f"Not found: {uri}")
        return record

    record = repository.get_optimized_cv_record(
        parsed["job_posting_identifier"], parsed["identifier"]
    )
    if record is None:
        raise ValueError(f"Not found: {uri}")
    return record
