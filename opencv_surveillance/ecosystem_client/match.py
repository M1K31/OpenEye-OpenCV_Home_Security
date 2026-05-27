def matches_pattern(event_type: str, pattern: str) -> bool:
    """Check if *event_type* matches a subscription *pattern*.

    Supported patterns:
    - ``"*"``          — matches everything
    - ``"security.*"`` — matches any type starting with ``security.``
    - ``"security.motion_detected"`` — exact match

    Empty strings never match.
    """
    if not event_type or not pattern:
        return False
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-1]  # e.g. "security."
        return event_type.startswith(prefix) or event_type == pattern[:-2]
    return event_type == pattern
