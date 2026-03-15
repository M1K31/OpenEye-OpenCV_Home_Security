def matches_pattern(event_type: str, pattern: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-2] + ".")
    return event_type == pattern
