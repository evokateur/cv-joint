import re


def kebab_case(name: str) -> str:
    """A CamelCase class name in kebab-case, the stem of files named after models."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()
