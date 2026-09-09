# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A stylesheet must not be keyed on state the application never sets.

Seven rules across TwoWayAudio.css and AudioModal.css were written against
`[data-theme="dark"]`. Nothing in the application ever sets that attribute —
ThemeContext applies `.<name>-theme` CLASSES to <html> and <body> — so the rules
never matched.

That was not merely dead weight. Every theme in themes.css has a dark
`--bg-panel`, and the base rules those overrides were meant to correct carried
light-theme values: `rgba(0, 0, 0, 0.1)` on a dark surface is invisible. The
spinner, the audio level meter's track and the diagnostics toggle's hover state
were therefore near-invisible in every theme, and the fix for it was sitting in
the file, unreachable.

A static check, deliberately. The frontend's own tests need node, which CI for
the backend does not have, and the property here — a selector that cannot match
— is decidable from the source.
"""

import pathlib
import re

import pytest

FRONTEND = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "src"


def _strip_css_comments(text: str) -> str:
    """
    Blank out comments while preserving line numbers.

    Deleting them outright shifts every subsequent line, so a reported location
    points at the wrong place — which it did on first run, naming two lines
    inside a comment block.
    """
    def blank(match):
        return "\n" * match.group(0).count("\n")

    return re.sub(r"/\*.*?\*/", blank, text, flags=re.S)


def _js_sources() -> str:
    parts = []
    for path in FRONTEND.rglob("*"):
        if path.suffix in {".js", ".jsx"} and "__tests__" not in path.parts:
            parts.append(path.read_text(errors="ignore"))
    return "\n".join(parts)


def _attribute_selectors_in_css():
    """Every [attr=...] selector used in a stylesheet, with its file and line."""
    found = []
    for path in sorted(FRONTEND.rglob("*.css")):
        for number, line in enumerate(_strip_css_comments(path.read_text()).splitlines(), 1):
            for match in re.finditer(r'\[([a-zA-Z-]+)\s*[~|^$*]?=', line):
                attribute = match.group(1)
                # Attributes the browser or the markup owns, not the app's state.
                if attribute in {"type", "disabled", "aria-hidden", "aria-expanded",
                                 "aria-selected", "aria-current", "role", "hidden",
                                 "open", "checked", "readonly", "placeholder",
                                 "aria-disabled", "aria-pressed", "data-testid"}:
                    continue
                found.append((path.relative_to(FRONTEND), number, attribute))
    return found


def test_no_stylesheet_keys_on_an_attribute_nothing_sets():
    """
    The finding: `[data-theme="dark"]` with no setAttribute('data-theme', ...).

    Checked generally rather than for that one attribute, so the next selector
    written against unset state is caught too.
    """
    js = _js_sources()
    unreachable = []

    for relative, number, attribute in _attribute_selectors_in_css():
        # `class` is set through classList, not setAttribute — and
        # html[class$="-theme"] in theme-bridge.css is exactly how the theme
        # classes are matched. Treating it as unset flagged working CSS.
        if attribute == "class":
            sets_it = "classList" in js
        else:
            sets_it = (
                f"setAttribute('{attribute}'" in js
                or f'setAttribute("{attribute}"' in js
                # JSX spelling: data-theme={...}
                or re.search(rf"\b{re.escape(attribute)}\s*=\s*[{{\"']", js) is not None
            )
        if not sets_it:
            unreachable.append(f"{relative}:{number} uses [{attribute}=...]")

    assert not unreachable, (
        "stylesheet rules key on an attribute the application never sets, so "
        "they can never match:\n  " + "\n  ".join(unreachable)
    )


def test_the_theme_mechanism_is_classes_not_attributes():
    """Pin the mechanism the CSS has to agree with."""
    context = FRONTEND / "context" / "ThemeContext.jsx"
    text = context.read_text()
    assert "classList.add" in text, "ThemeContext no longer applies theme classes"
    assert "setAttribute('data-theme'" not in text and \
           'setAttribute("data-theme"' not in text, (
        "ThemeContext now sets data-theme; the stylesheets removed in this "
        "change could be reinstated, but the two must agree either way"
    )


@pytest.mark.parametrize("stylesheet,selector", [
    ("components/TwoWayAudio.css", ".spinner"),
    ("components/TwoWayAudio.css", ".level-bar-container"),
    ("components/TwoWayAudio.css", ".diagnostics-toggle:hover"),
])
def test_dark_surface_overlays_are_light(stylesheet, selector):
    """
    The visual half of the bug.

    These sit on --bg-panel, which is dark in every theme themes.css defines, so
    a black overlay is invisible. The correct values existed only inside the
    unreachable block; they are now in the base rules.
    """
    text = _strip_css_comments((FRONTEND / stylesheet).read_text())
    start = text.index(selector + " {")
    body = text[start:text.index("}", start)]
    assert "rgba(0, 0, 0" not in body, (
        f"{selector} uses a black overlay on a dark panel; it will not be visible"
    )
