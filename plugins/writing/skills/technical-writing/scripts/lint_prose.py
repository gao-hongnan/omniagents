#!/usr/bin/env python3
"""
lint_prose.py: pattern checks for the technical-writing skill.

Flags the rules that a regular expression can catch in Markdown or plain-text
prose. It skips YAML front matter, fenced code, inline code, URLs, HTML tags,
and text inside double quotes, because those are exact strings or mentions,
not prose. It can't judge whether a sentence is clear, so read every hit as a
lead, not a verdict.

    python3 lint_prose.py README.md docs/guide.md
    python3 lint_prose.py --ignore will,passive docs/guide.md
    python3 lint_prose.py --list-rules
    python3 lint_prose.py --self-test

Errors are rules with few false positives. Warnings need a human look.
The exit code is 0 when there are no errors, 1 when there are errors (or
warnings, with --strict), and 2 for a usage error.

To skip a deliberate bad example, wrap it in HTML comments:

    <!-- lint-prose off -->
    > Simply run the script -- it will work.
    <!-- lint-prose on -->

Needs only the Python 3.9+ standard library.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from collections.abc import Iterator

# ASD-STE100 Issue 9 limits: instructions, descriptive sentences, paragraphs.
MAX_INSTRUCTION_WORDS = 20
MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 6
# A quoted mention longer than this is more likely a stray quotation mark.
MAX_QUOTE_CHARS = 300

ERROR, WARNING = "error", "warning"


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    summary: str


RULES = {
    r.name: r
    for r in [
        Rule("em-dash", ERROR, "an em dash, or a spaced double hyphen used as one"),
        Rule("semicolon", ERROR, "a semicolon in prose"),
        Rule("latin", ERROR, "e.g., i.e., etc., via, cf., viz., or N.B."),
        Rule("and-or", ERROR, '"and/or" outside a table'),
        Rule("optional-plural", ERROR, 'a plural written with "(s)"'),
        Rule("vague-link", ERROR, 'link text such as "here", "this", or "click here"'),
        Rule("minimizer", ERROR, '"simply", "obviously", or "of course"'),
        Rule("filler", ERROR, 'phrases such as "in order to" or "it is worth noting"'),
        Rule("hedge-stack", ERROR, 'stacked hedges such as "may potentially"'),
        Rule("assistant-talk", ERROR, 'chat phrases such as "I hope this helps"'),
        Rule("soft-minimizer", WARNING, '"just", "easy", "quick", "clearly", "basically", "actually", or "please"'),
        Rule("slop-word", WARNING, 'words such as "robust", "seamless", or "leverage"'),
        Rule("slash", WARNING, "a slash between two words, outside a table"),
        Rule("will", WARNING, '"will" where the present tense may fit'),
        Rule("should", WARNING, '"should", which reads as advice and as a rule'),
        Rule("ambiguous-word", WARNING, '"since", a leading "once", or a contrasting "while"'),
        Rule("timeless", WARNING, '"currently", "latest", "soon", and other words that go stale'),
        Rule("vague-this", WARNING, '"This" or "That" followed by a verb, with no noun'),
        Rule("passive", WARNING, "a form of be followed by a past participle"),
        Rule("sentence-length", WARNING, "an instruction over 20 words, or another sentence over 25"),
        Rule("paragraph-length", WARNING, "a paragraph of more than 6 sentences"),
        Rule("same-start", WARNING, "consecutive sentences that start with the same phrase"),
        Rule("heading-case", WARNING, "a heading in Title Case"),
        Rule("heading-gerund", WARNING, 'a heading that starts with an "-ing" word'),
        Rule("exclamation", WARNING, "an exclamation mark in prose"),
        Rule("placeholder-text", WARNING, "TODO, TBD, FIXME, XXX, or lorem ipsum"),
    ]
}


def _words(*words: str) -> re.Pattern[str]:
    """Compile words into one case-insensitive whole-word alternation."""
    return re.compile(r"(?i)\b(?:" + "|".join(words) + r")\b")


# Each pattern rule: (rule name, regex, message). Order sets the output order on a tie.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("em-dash", re.compile(r"—|(?<=\s)--(?=\s)"), "Replace the em dash with a period or a colon."),
    ("semicolon", re.compile(r";"), "Use a period, not a semicolon."),
    ("latin", re.compile(r"(?i)(?<![\w./])(?:e\.g\.|i\.e\.|etc\b\.?|cf\.|viz\.|n\.b\.)"),
     'Write "for example", "that is", or "such as", or say up front that the list is partial.'),
    ("latin", _words("via"), 'Write "through", "by", "with", or "using".'),
    ("and-or", _words("and/or"), 'Write "a, b, or both".'),
    ("optional-plural", re.compile(r"\b[A-Za-z]+\((?:s|es)\)"), "Pick the plural or the singular."),
    ("minimizer", _words("simply", "obviously", "of course"),
     "Cut it. What is simple for you might not be simple for the reader."),
    ("filler", _words(
        "in order to", r"it is (?:important|worth) (?:to note|noting)", r"it's (?:important to note|worth noting)",
        "it should be noted", "needless to say",
        r"as (?:mentioned|noted|discussed) (?:above|earlier|before|previously)",
        "at the end of the day", r"let's dive in", "dive into", r"in today's", "at its core", "when it comes to",
        "the fact that", r"in this (?:section|article|guide|post|document),? (?:we|you) will",
    ), "Cut the filler and state the fact."),
    ("hedge-stack", _words(
        r"(?:may|might|could|can) (?:potentially|possibly|perhaps|conceivably)",
        r"(?:potentially|possibly|perhaps) (?:may|might|could)",
        r"it (?:seems|appears) (?:that )?(?:it )?(?:may|might|could)",
    ), "Use one hedge, scoped to a named case, or none."),
    ("assistant-talk", re.compile(
        r"(?i)\b(?:great question|i hope this helps|hope this helps|let me know if|happy coding|as an ai|"
        r"feel free to)\b|\b(?:certainly|absolutely)!"
    ), "Delete it. Chat phrases don't belong in docs, commits, or PRs."),
    ("soft-minimizer", re.compile(
        r"(?i)\b(?:just(?!-)|easy|easily|quick|quickly|clearly|basically|actually|please)\b"
    ), "Cut it unless it carries meaning here."),
    ("slop-word", _words(
        "delve", "delves", "delving", "robust", "seamless", "seamlessly", "leverage", "leverages", "leveraging",
        "utilize", "utilizes", "utilization", "facilitate", "facilitates", "crucial", "pivotal", "tapestry",
        "testament", "cutting-edge", "state-of-the-art", "best-in-class", "world-class", "game-changer",
        "game-changing", "supercharge", "supercharges", "unleash", "empower", "empowers", "elevate", "elevates",
        "streamline", "streamlines", "myriad", "plethora", "ever-evolving", "fast-paced", "blazing", "synergy",
        "holistic", "paradigm", "comprehensive", "meticulous", "meticulously",
    ), "Replace it with the specific fact, or cut it."),
    ("will", _words("will", "won't"), "Use the present tense unless the event happens later."),
    ("should", _words("should", "shouldn't"),
     'Write "must" for a requirement, a command for an instruction, or "we recommend" for advice.'),
    ("ambiguous-word", _words("since"), 'Write "because" for a cause or "after" for a time.'),
    ("ambiguous-word", re.compile(r"(?:^|(?<=[.!?:]\s))Once\b"), 'Write "after" if you mean after.'),
    ("ambiguous-word", re.compile(r"(?i),\s+while\b"), 'Write "although" for a contrast.'),
    ("timeless", _words(
        "currently", "latest", "soon", "coming soon", "at the moment", "as of now", "in the future",
        "in a future release",
    ), "Document what exists, without words that go stale."),
    ("passive", re.compile(
        r"(?i)\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?"
        r"(?!(?:need|feed|seed|speed|indeed|embed|bed|red|shed)\b)"
        r"(?:\w{2,}ed|built|done|made|run|set|sent|kept|given|shown|written|known|seen|found|held|put|read|"
        r"taken|chosen|driven|hidden|broken|bound|brought|caught|drawn|forbidden|thrown|meant|paid|sold|"
        r"spent|split|told|thought|understood|won|withdrawn)\b"
    ), "Name the actor and make it the subject, unless the actor is unknown or beside the point."),
    ("exclamation", re.compile(r"[A-Za-z0-9)\]]!(?=\s|$)"), "End the sentence with a period."),
    ("placeholder-text", re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b|(?i:lorem ipsum)"),
     "Finish this before the doc ships."),
]
# Rules that a table cell may break: Google allows "and/or" where space is short.
TABLE_EXEMPT = {"and-or", "slash"}

SLASH = re.compile(r"(?<![\w/.~-])([A-Za-z]+)/([A-Za-z]+)(?![\w/.-])")
RATE_UNITS = {"s", "sec", "second", "ms", "us", "ns", "min", "minute", "h", "hr", "hour", "day", "d", "week",
              "month", "year", "yr", "op", "ops", "req", "call"}
# Established terms that contain a slash. Any other slash between words marks alternatives.
SLASH_TERMS = {"I/O", "CI/CD", "TCP/IP", "UDP/IP", "UI/UX", "A/B", "N/A", "PL/SQL"}
CODE_SPAN = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
LINK = re.compile(r"(!?)\[([^\]]*)\](?:\(([^)\s]*)(?:\s+\"[^\"]*\")?\)|\[[^\]]*\])")
URL = re.compile(r"<https?://[^>]+>|https?://\S+|www\.\S+")
HTML = re.compile(r"<!--.*?-->|</?[A-Za-z][^>]*>|&[A-Za-z]+;|&#\d+;", re.DOTALL)
QUOTED = re.compile(rf"\"[^\"]{{0,{MAX_QUOTE_CHARS}}}\"|“[^”]{{0,{MAX_QUOTE_CHARS}}}”")
VAGUE_LINK_TEXT = re.compile(r"(?i)^\s*(?:click here|here|this|this link|this page|link|read more|more|go here)\s*$")
VAGUE_THIS = re.compile(
    r"^(?:This|That|These|Those)\s+(?:is|are|was|were|means|makes|lets|allows|causes|leads|ensures|prevents|"
    r"gives|shows|happens|helps|keeps|breaks|fails|works|has|have|does|can|will|should|would|may|might|matters)\b"
)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
QUOTE_MARKERS = re.compile(r"^\s*(?:>\s?)+")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
TABLE_ROW = re.compile(r"^\s*\|")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
OFF = re.compile(r"<!--\s*lint-prose\s+off\s*-->")
ON = re.compile(r"<!--\s*lint-prose\s+on\s*-->")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(\[])")

# Words that Title Case capitalizes but sentence case leaves lowercase.
TITLE_CASE_TELLS = {
    "a", "an", "the", "and", "or", "but", "for", "nor", "on", "at", "to", "from", "by", "of", "in", "into",
    "with", "without", "over", "under", "about", "after", "before", "your", "you", "our", "we", "it", "its",
    "this", "that", "these", "those", "how", "what", "why", "when", "where", "which", "who", "is", "are", "be",
    "use", "using", "set", "up", "get", "getting", "started", "start", "create", "run", "add", "make", "new",
    "guide", "overview", "reference", "introduction", "install", "configure", "build", "test", "write", "read",
    "work", "works", "more", "not", "all", "first", "next", "step", "steps", "example", "examples", "tips",
    "best", "practices", "common", "basic", "advanced", "quick", "simple", "data", "file", "files", "page",
}
NOT_GERUNDS = {"string", "strings", "thing", "things", "nothing", "something", "anything", "everything",
               "ring", "king", "bring", "spring", "swing", "wing", "sing", "sting", "during", "ceiling",
               "evening", "morning", "missing"}
IMPERATIVE_VERBS = {
    "add", "apply", "back", "build", "call", "change", "check", "choose", "click", "close", "commit", "configure",
    "confirm", "copy", "create", "define", "delete", "deploy", "disable", "download", "edit", "enable", "enter",
    "export", "give", "go", "import", "install", "keep", "link", "list", "log", "make", "move", "name", "open",
    "pass", "pick", "press", "pull", "push", "put", "read", "remove", "rename", "replace", "restart", "return",
    "run", "save", "select", "set", "sign", "specify", "split", "start", "stop", "test", "type", "update",
    "upload", "use", "verify", "write",
}
ARTICLES = {"the", "a", "an"}
PLACEHOLDER_WORDS = {"q", "code"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    col: int
    rule: str
    message: str
    excerpt: str

    def render(self) -> str:
        severity = RULES[self.rule].severity
        excerpt = f" [{self.excerpt}]" if self.excerpt else ""
        return f"{self.path}:{self.line}:{self.col}: {severity} {self.rule}: {self.message}{excerpt}"


def _mask(span: str, head: str = "") -> str:
    """Blank a span but keep its newlines, so lines and columns still line up."""
    body = "".join("\n" if ch == "\n" else " " for ch in span)
    first_line = body.find("\n")
    room = len(body) if first_line == -1 else first_line
    return head[:room] + body[min(len(head), room):] if head else body


@dataclass
class Cleaned:
    """Prose with every non-prose span blanked, and the link labels that it held."""
    text: str
    links: list[tuple[int, str]] = field(default_factory=list)


def clean(text: str) -> Cleaned:
    """Blank code, URLs, HTML, and quoted mentions. Keep link labels. Preserve length and newlines."""
    text = CODE_SPAN.sub(lambda m: _mask(m.group(0), "CODE"), text)
    text = HTML.sub(lambda m: _mask(m.group(0)), text)
    links: list[tuple[int, str]] = []

    def keep_label(match: re.Match[str]) -> str:
        image, label = match.group(1), match.group(2)
        if not image:
            links.append((match.start() + 1, label))
        return _mask(match.group(0), " " + label.replace("\n", " "))

    text = LINK.sub(keep_label, text)
    text = URL.sub(lambda m: _mask(m.group(0)), text)
    text = QUOTED.sub(lambda m: _mask(m.group(0), "Q"), text)
    text = text.replace("**", "  ").replace("__", "  ")
    return Cleaned(text, links)


def iter_lines(raw: str) -> Iterator[tuple[int, str, str]]:
    """Yield (line number, kind, text), where kind is prose, heading, table, blank, or skip."""
    lines = raw.splitlines()
    in_front_matter = bool(lines) and lines[0].strip() == "---"
    fence: str | None = None
    off = in_comment = False
    for number, line in enumerate(lines, start=1):
        if in_front_matter:
            if number > 1 and line.strip() in ("---", "..."):
                in_front_matter = False
            yield number, "skip", line
        elif fence is not None:
            if line.strip().startswith(fence) and not line.strip().strip(fence[0]):
                fence = None
            yield number, "skip", line
        elif ON.search(line):
            off = False
            yield number, "skip", line
        elif OFF.search(line):
            off = True
            yield number, "skip", line
        elif off:
            yield number, "skip", line
        elif FENCE.match(line):
            marker = FENCE.match(line)
            fence = marker.group(1) if marker else "```"
            yield number, "skip", line
        elif in_comment:
            in_comment = "-->" not in line
            yield number, "skip", line
        elif line.lstrip().startswith("<!--") and "-->" not in line:
            in_comment = True
            yield number, "skip", line
        else:
            # Classify a blockquote line by its content, so that a bare ">" ends a paragraph.
            inner = QUOTE_MARKERS.sub("", line)
            if not inner.strip():
                yield number, "blank", line
            elif TABLE_RULE.match(inner):
                yield number, "skip", line
            elif TABLE_ROW.match(inner):
                yield number, "table", inner
            elif HEADING.match(inner):
                yield number, "heading", inner
            else:
                yield number, "prose", line


def check_patterns(path: str, number: int, text: str, in_table: bool) -> Iterator[Finding]:
    for rule, pattern, message in PATTERNS:
        if in_table and rule in TABLE_EXEMPT:
            continue
        for match in pattern.finditer(text):
            yield Finding(path, number, match.start() + 1, rule, message, match.group(0).strip())
    if in_table:
        return
    for match in SLASH.finditer(text):
        left, right = match.group(1), match.group(2)
        if left.lower() == "and" and right.lower() == "or":
            continue  # "and/or" has its own rule.
        if f"{left}/{right}".upper() in SLASH_TERMS or right.lower() in RATE_UNITS:
            continue  # Terms such as I/O and CI/CD, and rates such as req/s.
        yield Finding(path, number, match.start() + 1, "slash",
                      'Write "a or b", "a and b", or "a, b, or both". Put a path in code font.', match.group(0))


def check_heading(path: str, number: int, heading: str) -> Iterator[Finding]:
    text = clean(heading).text
    words = re.findall(r"[A-Za-z][A-Za-z'-]*|:", text)
    sentence_start = True
    tells = []
    for word in words:
        if word == ":":
            sentence_start = True
            continue
        if not sentence_start and word[0].isupper() and word[1:].islower() and word.lower() in TITLE_CASE_TELLS:
            tells.append(word)
        sentence_start = False
    if tells:
        yield Finding(path, number, 1, "heading-case", "Use sentence case.", " ".join(tells))
    # In a compound such as "Machine-writing", the first part decides.
    first = next((w for w in words if w != ":"), "").split("-")[0]
    if first.lower().endswith("ing") and len(first) > 4 and first.lower() not in NOT_GERUNDS:
        yield Finding(path, number, 1, "heading-gerund",
                      "Start a task heading with a bare verb, and a concept heading with a noun.", first)
    yield from check_patterns(path, number, text, in_table=False)


def is_instruction(sentence: str) -> bool:
    words = re.sub(r"^Optional:\s*", "", sentence).split()
    if not words:
        return False
    first = words[0].strip("*_").lower()
    if first in IMPERATIVE_VERBS:
        return True
    if first in ("to", "if", "before", "after", "when", "in") and "," in sentence:
        rest = sentence.split(",", 1)[1].split()
        return bool(rest) and rest[0].strip("*_").lower() in IMPERATIVE_VERBS
    return False


def opening_phrase(sentence: str) -> str:
    """The first word, or the first two when the first is an article."""
    words = [w.strip("*_\"'()").lower() for w in sentence.split()]
    if not words or words[0] in PLACEHOLDER_WORDS:
        return ""
    return " ".join(words[:2]) if words[0] in ARTICLES else words[0]


def check_sentences(path: str, text: str, line_of: list[int]) -> Iterator[Finding]:
    """Run the sentence and paragraph rules on one block of prose."""
    sentences: list[tuple[int, str]] = []
    start = 0
    for end in [m.start() for m in SENTENCE_END.finditer(text)] + [len(text)]:
        piece = text[start:end]
        if piece.strip():
            offset = start + len(piece) - len(piece.lstrip())
            sentences.append((line_of[min(offset, len(line_of) - 1)], piece.strip()))
        match = SENTENCE_END.match(text, end) if end < len(text) else None
        start = match.end() if match else end
    previous = ""
    for line, sentence in sentences:
        words = [w for w in sentence.split() if re.search(r"[A-Za-z0-9]", w)]
        limit = MAX_INSTRUCTION_WORDS if is_instruction(sentence) else MAX_SENTENCE_WORDS
        if len(words) > limit:
            kind = "instruction" if limit == MAX_INSTRUCTION_WORDS else "sentence"
            yield Finding(path, line, 1, "sentence-length",
                          f"This {kind} has {len(words)} words. Split it at {limit} or fewer.",
                          " ".join(words[:8]) + " ...")
        if VAGUE_THIS.match(sentence):
            yield Finding(path, line, 1, "vague-this", 'Put a noun after "this" or "that".', " ".join(words[:2]))
        phrase = opening_phrase(sentence)
        if phrase and phrase == previous:
            yield Finding(path, line, 1, "same-start", "Vary the start of consecutive sentences.", phrase)
        previous = phrase
    if len(sentences) > MAX_PARAGRAPH_SENTENCES:
        yield Finding(path, sentences[0][0], 1, "paragraph-length",
                      f"This paragraph has {len(sentences)} sentences. Keep one topic in "
                      f"{MAX_PARAGRAPH_SENTENCES} or fewer.", "")


def check_block(path: str, block: list[tuple[int, str]]) -> Iterator[Finding]:
    """Check one paragraph or list item, given as (line number, raw line) pairs."""
    stripped = []
    for index, (_, line) in enumerate(block):
        line = QUOTE_MARKERS.sub(lambda m: " " * len(m.group(0)), line)
        if index == 0:
            line = LIST_ITEM.sub(lambda m: " " * len(m.group(0)), line)
        stripped.append(line)
    cleaned = clean("\n".join(stripped))
    lines = cleaned.text.split("\n")
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    for offset, label in cleaned.links:
        if VAGUE_LINK_TEXT.match(label):
            row = max(i for i, s in enumerate(starts) if s < offset)
            yield Finding(path, block[row][0], offset - starts[row], "vague-link",
                          "Make the link text say where the link goes.", label)
    line_of: list[int] = []
    for (number, _), line in zip(block, lines):
        yield from check_patterns(path, number, line, in_table=False)
        line_of.extend([number] * (len(line) + 1))
    yield from check_sentences(path, cleaned.text.replace("\n", " "), line_of)


def lint_text(path: str, raw: str) -> list[Finding]:
    findings: list[Finding] = []
    block: list[tuple[int, str]] = []

    def flush() -> None:
        if block:
            findings.extend(check_block(path, block))
            block.clear()

    for number, kind, line in iter_lines(raw):
        if kind == "prose":
            if block and LIST_ITEM.match(QUOTE_MARKERS.sub("", line)):
                flush()
            block.append((number, line))
            continue
        flush()
        heading = HEADING.match(line) if kind == "heading" else None
        if heading:
            findings.extend(check_heading(path, number, heading.group(2)))
        elif kind == "table":
            cleaned = clean(line)
            findings.extend(check_patterns(path, number, cleaned.text, in_table=True))
            for offset, label in cleaned.links:
                if VAGUE_LINK_TEXT.match(label):
                    findings.append(Finding(path, number, offset, "vague-link",
                                            "Make the link text say where the link goes.", label))
    flush()
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings


SELF_TESTS: list[tuple[str, set[str]]] = [
    ("Use the tool — it works.", {"em-dash"}),
    ("Run the build; then deploy it.", {"semicolon"}),
    ("Pick a format, e.g. JSON.", {"latin"}),
    ("Send the file via email.", {"latin"}),
    ("Edit the hosts file in /etc/hosts.", set()),
    ("Rotate the API key(s) monthly.", {"optional-plural"}),
    ("You can view and/or edit your data.", {"and-or"}),
    ("Choose the client/server mode.", {"slash"}),
    ("Measure I/O at 500 req/s.", set()),
    ("Run the CI/CD pipeline.", set()),
    ("Set the TTL/size limits.", {"slash"}),
    ("Load the JSON/YAML files.", {"slash"}),
    ("Ship it w/o the tests.", {"slash"}),
    ("Read the [guide](https://example.com) first.", set()),
    ("Read [here](https://example.com) first.", {"vague-link"}),
    ("Simply run the script.", {"minimizer"}),
    ("In order to deploy, run the script.", {"filler"}),
    ("The job may potentially fail.", {"hedge-stack"}),
    ("I hope this helps.", {"assistant-talk"}),
    ("Compile it just-in-time.", set()),
    ("The server will restart at midnight.", {"will"}),
    ("The file is deleted by the cleanup job.", {"passive"}),
    ("Since the cache is cold, reads are slow.", {"ambiguous-word"}),
    ("Once the build ends, deploy it.", {"ambiguous-word"}),
    ("Reads are fast, while writes are slow.", {"ambiguous-word"}),
    ("This means the cache is cold.", {"vague-this"}),
    ("Our robust parser handles every case.", {"slop-word"}),
    ("The feature is currently in beta.", {"timeless"}),
    ("It works! Run it now.", {"exclamation"}),
    ("Finish the TODO list first.", {"placeholder-text"}),
    ("Run `a; b` in a shell.", set()),
    ('Write "in order to" as "to".', set()),
    ('Write "in order\nto" as "to".', set()),
    ("Run `a;\nb` in a shell.", set()),
    ("```\nfoo; bar — baz\n```", set()),
    ("<!-- lint-prose off -->\nSimply do it — now.\n<!-- lint-prose on -->", set()),
    ("See https://example.com/a/b;c for the spec.", set()),
    ("Edit `docs/a/b.md` and commit the change.", set()),
    ("## Getting Started With Docker", {"heading-case", "heading-gerund"}),
    ("## Configure Docker and GitHub Actions", set()),
    ("## Step 2: Install the tool", set()),
    ("The parser reads the file. The parser checks the header.", {"same-start"}),
    ("The parser reads the file. The header comes first.", set()),
    ("- Use one name.\n- Use one verb.", set()),
    ("Run the script with the verbose flag and the dry-run flag so that you can see each file it would change.",
     {"sentence-length"}),
    ("The parser reads each line of the file, checks the header against the schema, and records every field "
     "that fails to match in the error log.", {"sentence-length"}),
    ("A. One. Two. Three. Four. Five. Six. Seven.", {"paragraph-length"}),
    ("| a/b | c and/or d |\n| --- | --- |\n| x | y |", set()),
    ("> Simply run it.", {"minimizer"}),
    ("## Machine-writing tells", set()),
    ("> ## Getting Started", {"heading-case", "heading-gerund"}),
    # A bare ">" ends the paragraph. Joined, these two lines would make one 30-word sentence.
    ("> - Restart the client and the server and then check that each of them reports a healthy status\n>\n"
     "> then check the logs and the metrics and the alerts and the dashboards.", set()),
]


def self_test() -> int:
    failures = 0
    for text, expected in SELF_TESTS:
        got = {f.rule for f in lint_text("<test>", text)}
        if got != expected:
            failures += 1
            print(f"FAIL {text!r}\n     expected {sorted(expected)}, got {sorted(got)}")
    print(f"{len(SELF_TESTS) - failures}/{len(SELF_TESTS)} self-tests passed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pattern checks for the technical-writing skill.")
    parser.add_argument("paths", nargs="*", help="Markdown or text files. Use - for standard input.")
    parser.add_argument("--ignore", default="", help="Comma-separated rule names to skip.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings too.")
    parser.add_argument("--list-rules", action="store_true", help="Print every rule and exit.")
    parser.add_argument("--self-test", action="store_true", help="Run the built-in cases and exit.")
    args = parser.parse_args(argv)

    if args.list_rules:
        for rule in RULES.values():
            print(f"{rule.name:<18} {rule.severity:<8} {rule.summary}")
        return 0
    if args.self_test:
        return self_test()
    if not args.paths:
        parser.error("give at least one file, or - for standard input")

    ignored = {name.strip() for name in args.ignore.split(",") if name.strip()}
    unknown = ignored - set(RULES)
    if unknown:
        parser.error(f"unknown rule names: {', '.join(sorted(unknown))}")

    errors = warnings = 0
    for path in args.paths:
        try:
            if path == "-":
                raw = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as handle:
                    raw = handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: can't read: {exc}", file=sys.stderr)
            return 2
        for finding in lint_text(path, raw):
            if finding.rule in ignored:
                continue
            print(finding.render())
            if RULES[finding.rule].severity == ERROR:
                errors += 1
            else:
                warnings += 1
    print(f"{errors} errors, {warnings} warnings in {len(args.paths)} files")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
