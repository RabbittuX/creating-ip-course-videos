#!/usr/bin/env python3
"""Shared deterministic caption boundary rules."""

import hashlib
import re
import unicodedata
from pathlib import Path


EDGE_PUNCTUATION = "，。！？；：、,.!?;: \t\r\n"
HARD_PUNCTUATION = "。！？!?；;\n"  # a line break in the script is a paragraph end
TURN_WORDS = (
    "但是", "不过", "然而", "所以", "因此", "接下来", "然后", "另外",
    "同时", "反过来", "换句话说", "第一", "第二", "第三", "最后",
)
DEFAULT_PROTECTED_TERMS = ("Skill", "SKILL.md", "references", "scripts", "assets", "MCP")


def _protected_terms():
    try:
        from user_config import load_config
        extra = [t for t in load_config().get("captions", {}).get("protectedTerms", []) if not str(t).startswith("填")]
    except Exception:
        extra = []
    return tuple(dict.fromkeys([*DEFAULT_PROTECTED_TERMS, *[str(t) for t in extra if t]]))


PROTECTED_TERMS = _protected_terms()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trim_span(text, start, end):
    while start < end and text[start] in EDGE_PUNCTUATION:
        start += 1
    while end > start and text[end - 1] in EDGE_PUNCTUATION:
        end -= 1
    return start, end


def is_sentence_stop(text, index):
    char = text[index]
    if char not in HARD_PUNCTUATION:
        return False
    if char == "." and index > 0 and index + 1 < len(text):
        return not (text[index - 1].isascii() and text[index - 1].isalnum() and text[index + 1].isascii() and text[index + 1].isalnum())
    return True


LATIN_TERM = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_@+]|[.\-/](?=[A-Za-z0-9]))*")


def protected_spans(text, start, end):
    # Any Latin/number run (A-roll, Node.js, 2.0, generate.py, @pippit-dev/cli) is one unbreakable term.
    spans = [(m.start(), m.end()) for m in LATIN_TERM.finditer(text, start, end) if m.end() - m.start() > 1]
    lower = text.lower()
    for term in PROTECTED_TERMS:
        cursor = start
        needle = term.lower()
        while True:
            at = lower.find(needle, cursor, end)
            if at < 0:
                break
            spans.append((at, at + len(term)))
            cursor = at + len(term)
    return spans


def inside_protected(position, spans):
    return any(start < position < end for start, end in spans)


def semantic_spans(text, max_chars=22):
    hard = []
    start = 0
    for index in range(len(text)):
        if is_sentence_stop(text, index):
            span = trim_span(text, start, index)
            if span[0] < span[1]:
                hard.append(span)
            start = index + 1
    span = trim_span(text, start, len(text))
    if span[0] < span[1]:
        hard.append(span)

    clauses = []
    for start, end in hard:
        cuts = [start]
        for word in TURN_WORDS:
            cursor = start + 1
            while True:
                at = text.find(word, cursor, end)
                if at < 0:
                    break
                prefix = text[at - 1] if at > start else ""
                if prefix in "，,；;：: \t\r\n":
                    cuts.append(at)
                cursor = at + len(word)
        cuts.append(end)
        for left, right in zip(sorted(set(cuts)), sorted(set(cuts))[1:]):
            trimmed = trim_span(text, left, right)
            if trimmed[0] < trimmed[1]:
                clauses.append(trimmed)

    result = []
    for start, end in clauses:
        cursor = start
        protected = protected_spans(text, start, end)
        while end - cursor > max_chars:
            limit = cursor + max_chars
            candidates = [index + 1 for index in range(cursor, min(limit, end)) if text[index] in "，,；;：:、 "]
            cut = max(candidates, default=limit)
            while cut > cursor and inside_protected(cut, protected):
                cut -= 1
            if cut <= cursor:
                cut = limit
                while cut < end and inside_protected(cut, protected):
                    cut += 1
            piece = trim_span(text, cursor, cut)
            if piece[0] < piece[1]:
                result.append(piece)
            cursor = cut
        piece = trim_span(text, cursor, end)
        if piece[0] < piece[1]:
            result.append(piece)
    return result


def broken_term_at(text, start, end):
    """Return the Latin/number term a caption boundary cuts through, if any."""
    for position in (start, end):
        for match in LATIN_TERM.finditer(text, max(0, position - 40), min(len(text), position + 40)):
            if match.start() < position < match.end():
                return text[match.start():match.end()]
    return None


def has_semantic_join(text):
    if any(is_sentence_stop(text, index) for index in range(len(text))):
        return "同一条字幕包含两句以上完整语义"
    pattern = r"[，,；;：:]\s*(" + "|".join(map(re.escape, TURN_WORDS)) + r")"
    match = re.search(pattern, text)
    if match:
        return f"转折词“{match.group(1)}”应换字幕"
    return None


def token_at_char(position, tokens):
    covering = [token for token in tokens if int(token.get("charStart", -1)) <= position < int(token.get("charEnd", -1))]
    if covering:
        return covering[0]
    following = [token for token in tokens if int(token.get("charStart", -1)) >= position]
    return following[0] if following else None


def estimated_width_px(text, font_size=42):
    units = 0.0
    for char in text:
        units += 1.0 if unicodedata.east_asian_width(char) in {"W", "F", "A"} else 0.58
    return round(units * font_size, 1)
