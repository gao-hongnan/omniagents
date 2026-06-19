#!/usr/bin/env python3
"""Schema, validation, and JSON->Markdown renderer for the research plugin.

This is the machine-enforceable half of the ``research-contract`` skill: JSON is
the canonical artifact every retriever and gate produces, and the human-readable
Markdown report is *rendered* from that JSON by this script. The prose half (tier
rubric, confidence rubric, safety rails, authoring guidance) lives beside this
file in ``SKILL.md``.

Stdlib only -- no pydantic, no jinja2 -- so it runs under any Python 3.11+
interpreter without a virtualenv (the plugin ships none).

Parse, don't validate: raw JSON is parsed *once* at the boundary into frozen,
fully-typed domain objects (``Citation``, ``Claim``, ``Hypothesis``,
``RetrieverReport``, ``ResearchReport``) by ``from_json`` smart constructors that
raise ``ContractError`` on the first bad field. Everything downstream -- counting,
grouping, Markdown rendering -- operates on those typed objects, so a renderer
never re-reads or re-coerces an untyped dict. The single untyped value in the
program is the ``object`` that ``json.loads`` returns; it is narrowed immediately
and never propagates.

The Iron Law in code: a ``Citation`` without a resolvable ``identifier`` and a
non-empty ``quote`` fails to parse, and a grounded ``Claim`` must carry at least
one ``Citation``. So a claim a human reads always has a source they can open and a
sentence they can check -- "no source = no claim" is enforced here, not trusted.

Shapes
------
Citation (leaf):
    identifier  "PMID:<n>" | "DOI:<doi>" | "PMCID:<id>" | "NCT:<id>"  (required)
    url         deterministic resolver URL                            (required)
    quote       verbatim supporting sentence                          (required)
    locator     section/paragraph/page                                (optional)
    source_type one of the SourceType enum                            (optional)
    peer_reviewed  bool (default True)                                (optional)
    retracted   bool (default False)                                  (optional)

Claim (grounded):
    statement, sub_question, summary-of-evidence note                 (required)
    tier        ESTABLISHED | EMERGING | CONTESTED | SPECULATIVE      (required)
    grade       HIGH | MODERATE | LOW | VERY_LOW                      (required)
    ocebm_level "1".."5" | null                                       (optional)
    citations   [Citation], non-empty                                 (required)
    support     ENTAILED | PARTIAL | UNSUPPORTED                      (required)
    confidence  int 0..100                                            (required)
    case_definition, commercial_conflict, note                       (optional)

Hypothesis (hypothesis mode; lives in hypotheses[], never claims[]):
    statement, discriminating_test, falsification                     (required)
    chain       [ChainEdge], non-empty, each edge cites a citation    (required)
    citations   [Citation], non-empty                                 (required)
    tier        always SPECULATIVE                                    (required)
    novelty     novel | established                                   (optional)
    assumptions, competing (>=1), confidence                          (req: competing)

RetrieverReport (one per sub-question):
    sub_question, question, date, claims: [Claim], summary

ResearchReport (final, adjudicator output):
    question, date, author, mode, disclaimer, executive_summary,
    claims: [Claim], hypotheses: [Hypothesis],
    contested: [{topic, positions}], safety_flags: [{intervention, harm, ...}],
    open_questions: [str], audit: {sub_questions, searches, claims_dropped, ...}

CLI
---
    python3 schema.py notes  <json> [out.md]     # render one retriever report
    python3 schema.py report <json> [out.md]     # render the final report
    python3 schema.py --schema                    # print this annotated shape

Invalid input exits non-zero naming the offending field/index and writes no .md,
so a caller can surface the error instead of persisting a broken report.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Self, TypeGuard, TypeVar

# -- closed sets ------------------------------------------------------------


class Tier(StrEnum):
    ESTABLISHED = "ESTABLISHED"
    EMERGING = "EMERGING"
    CONTESTED = "CONTESTED"
    SPECULATIVE = "SPECULATIVE"


class Grade(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class Support(StrEnum):
    ENTAILED = "ENTAILED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


class SourceType(StrEnum):
    SYSTEMATIC_REVIEW = "systematic-review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_SERIES = "case-series"
    PREPRINT = "preprint"
    TRIAL_REGISTRY = "trial-registry"
    GUIDELINE = "guideline"
    PATIENT_LED = "patient-led"
    MECHANISM = "mechanism"
    OTHER = "other"


class Novelty(StrEnum):
    NOVEL = "novel"
    ESTABLISHED = "established"


class Mode(StrEnum):
    GROUNDED = "grounded"
    HYPOTHESIS = "hypothesis"


class ContractError(ValueError):
    """Raised when a JSON payload violates the research contract."""


# Identifier prefixes the verifier knows how to resolve (Gate 1). A citation
# whose identifier carries none of these cannot be existence-checked.
_ID_PREFIXES: Final = ("PMID:", "DOI:", "PMCID:", "NCT:")

# OCEBM 2011 study-design levels, as strings (a level is a label, not a count).
_OCEBM_LEVELS: Final = ("1", "2", "3", "4", "5")


# -- domain model -----------------------------------------------------------
#
# Each type is frozen and only constructible (in practice) through `from_json`,
# the boundary parser: once an instance exists every field is the right type and
# present, so renderers below need no defensive `.get()`.


@dataclass(frozen=True, slots=True)
class Citation:
    """One source backing a claim. Always valid once built via `from_json`."""

    identifier: str
    url: str
    quote: str
    locator: str
    source_type: SourceType
    peer_reviewed: bool
    retracted: bool

    @classmethod
    def from_json(cls: type[Self], raw: object, ctx: str) -> Self:
        data = _require_object(raw, ctx)
        identifier = _req_str(data, "identifier", ctx)
        if not any(identifier.upper().startswith(p) for p in _ID_PREFIXES):
            raise ContractError(
                f"{ctx}: identifier {identifier!r} must start with one of "
                f"{_ID_PREFIXES} so the verifier can resolve it"
            )
        url = _req_str(data, "url", ctx)
        # The Iron Law: existence (identifier) is not support -- a quote is what a
        # human and Gate 2 check the claim against. No quote => not a citation.
        quote = _req_str(data, "quote", ctx)
        source_type = _parse_enum_default(
            SourceType, data.get("source_type"), SourceType.OTHER, "source_type", ctx
        )
        return cls(
            identifier=identifier,
            url=url,
            quote=quote,
            locator=_opt_str(data, "locator"),
            source_type=source_type,
            peer_reviewed=_opt_bool(data, "peer_reviewed", default=True),
            retracted=_opt_bool(data, "retracted", default=False),
        )

    def render(self) -> str:
        flags = ""
        if self.retracted:
            flags += " ⚠️RETRACTED"
        if not self.peer_reviewed:
            flags += " (not peer-reviewed)"
        loc = f", {self.locator}" if self.locator else ""
        return f'[{self.identifier}]({self.url}){flags} — "{self.quote}"{loc}'


@dataclass(frozen=True, slots=True)
class Claim:
    """One grounded, graded, cited claim."""

    statement: str
    tier: Tier
    grade: Grade
    ocebm_level: str | None
    sub_question: str
    citations: tuple[Citation, ...]
    support: Support
    confidence: int
    case_definition: str
    commercial_conflict: str
    note: str

    @classmethod
    def from_json(cls: type[Self], raw: object, idx: int) -> Self:
        ctx = f"claim[{idx}]"
        data = _require_object(raw, ctx)
        statement = _req_str(data, "statement", ctx)
        tier = _parse_enum(Tier, data.get("tier"), "tier", ctx)
        grade = _parse_enum(Grade, data.get("grade"), "grade", ctx)

        ocebm_level: str | None = None
        ocebm_raw = data.get("ocebm_level")
        if ocebm_raw is not None:
            ocebm_level = str(ocebm_raw)
            if ocebm_level not in _OCEBM_LEVELS:
                raise ContractError(
                    f"{ctx}: ocebm_level must be one of {_OCEBM_LEVELS} or null, "
                    f"got {ocebm_raw!r}"
                )

        sub_question = _req_str(data, "sub_question", ctx)
        citations = _parse_citations(data.get("citations"), ctx)
        if not citations:
            raise ContractError(
                f"{ctx}: a grounded claim needs >=1 citation (the Iron Law: "
                "no source = no claim)"
            )
        support = _parse_enum(Support, data.get("support"), "support", ctx)
        confidence = _parse_confidence(data.get("confidence"), ctx)
        return cls(
            statement=statement,
            tier=tier,
            grade=grade,
            ocebm_level=ocebm_level,
            sub_question=sub_question,
            citations=citations,
            support=support,
            confidence=confidence,
            case_definition=_opt_str(data, "case_definition"),
            commercial_conflict=_opt_str(data, "commercial_conflict"),
            note=_opt_str(data, "note"),
        )

    def render(self) -> str:
        ocebm = f" · OCEBM {self.ocebm_level}" if self.ocebm_level else ""
        head = (
            f"- **[{self.tier.value}]** {self.statement} "
            f"_(GRADE {self.grade.value}{ocebm} · support {self.support.value} · "
            f"confidence {self.confidence})_"
        )
        lines = [head]
        if self.case_definition:
            lines.append(f"  - **Case definition**: {self.case_definition}")
        if self.commercial_conflict and self.commercial_conflict.lower() != "none":
            lines.append(f"  - **Commercial conflict**: {self.commercial_conflict}")
        if self.note:
            lines.append(f"  - **Note**: {self.note}")
        for cit in self.citations:
            lines.append(f"  - {cit.render()}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ChainEdge:
    """One directed, cited link of a hypothesis's mechanistic chain."""

    src: str
    relation: str
    dst: str
    citation: int

    @classmethod
    def from_json(cls: type[Self], raw: object, ctx: str, n_citations: int) -> Self:
        data = _require_object(raw, ctx)
        citation = _coerce_int(data.get("citation"))
        if citation is None or not 0 <= citation < n_citations:
            raise ContractError(
                f"{ctx}: citation must index into the hypothesis citations "
                f"(0..{n_citations - 1}); an uncited edge is a fabricated fact"
            )
        return cls(
            src=_req_str(data, "from", ctx),
            relation=_req_str(data, "relation", ctx),
            dst=_req_str(data, "to", ctx),
            citation=citation,
        )

    def render(self) -> str:
        return f"{self.src} —{self.relation}→ {self.dst} [{self.citation}]"


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A literature-based-discovery hypothesis: novel connection, cited edges."""

    statement: str
    chain: tuple[ChainEdge, ...]
    citations: tuple[Citation, ...]
    novelty: Novelty
    assumptions: tuple[str, ...]
    competing: tuple[str, ...]
    discriminating_test: str
    falsification: str
    confidence: int

    @classmethod
    def from_json(cls: type[Self], raw: object, idx: int) -> Self:
        ctx = f"hypothesis[{idx}]"
        data = _require_object(raw, ctx)
        tier = _parse_enum(Tier, data.get("tier"), "tier", ctx)
        if tier is not Tier.SPECULATIVE:
            raise ContractError(
                f"{ctx}: a hypothesis is always SPECULATIVE (got {tier.value}); "
                "grounded conclusions belong in claims[]"
            )
        citations = _parse_citations(data.get("citations"), ctx)
        if not citations:
            raise ContractError(f"{ctx}: a hypothesis needs >=1 cited edge source")
        chain = _parse_chain(data.get("chain"), ctx, len(citations))
        competing = _parse_str_list(data.get("competing"))
        if not competing:
            raise ContractError(
                f"{ctx}: list >=1 competing explanation (Strong Inference: never "
                "advance a single pet mechanism)"
            )
        return cls(
            statement=_req_str(data, "statement", ctx),
            chain=chain,
            citations=citations,
            novelty=_parse_enum_default(
                Novelty, data.get("novelty"), Novelty.ESTABLISHED, "novelty", ctx
            ),
            assumptions=_parse_str_list(data.get("assumptions")),
            competing=competing,
            discriminating_test=_req_str(data, "discriminating_test", ctx),
            falsification=_req_str(data, "falsification", ctx),
            confidence=_parse_confidence(data.get("confidence"), ctx),
        )

    def render(self) -> str:
        badge = " · **NOVEL**" if self.novelty is Novelty.NOVEL else ""
        lines = [
            f"- **{self.statement}** _(SPECULATIVE — hypothesis, not a finding"
            f"{badge} · confidence {self.confidence})_",
            f"  - **Chain**: {' ; '.join(e.render() for e in self.chain)}",
        ]
        if self.assumptions:
            lines.append("  - **Assumptions**: " + "; ".join(self.assumptions))
        lines.append("  - **Competing**: " + "; ".join(self.competing))
        lines.append(f"  - **Discriminating test**: {self.discriminating_test}")
        lines.append(f"  - **Falsification**: {self.falsification}")
        for i, cit in enumerate(self.citations):
            lines.append(f"  - [{i}] {cit.render()}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class SafetyFlag:
    """A harmful or predatory intervention surfaced rather than relayed."""

    intervention: str
    harm: str
    commercial: str
    note: str

    @classmethod
    def from_json(cls: type[Self], raw: object, idx: int) -> Self:
        ctx = f"safety_flags[{idx}]"
        data = _require_object(raw, ctx)
        return cls(
            intervention=_req_str(data, "intervention", ctx),
            harm=_req_str(data, "harm", ctx),
            commercial=_opt_str(data, "commercial"),
            note=_opt_str(data, "note"),
        )

    def render(self) -> str:
        bits = [f"- **{self.intervention}** — {self.harm}"]
        if self.commercial and self.commercial.lower() not in ("", "n/a", "none"):
            bits.append(f"profits: {self.commercial}")
        if self.note:
            bits.append(self.note)
        return " · ".join(bits)


@dataclass(frozen=True, slots=True)
class ContestedTopic:
    """A genuine disagreement, all sides presented with each side's grade."""

    topic: str
    positions: tuple[tuple[str, str, str], ...]  # (stance, grade, note)

    @classmethod
    def from_json(cls: type[Self], raw: object, idx: int) -> Self:
        ctx = f"contested[{idx}]"
        data = _require_object(raw, ctx)
        positions_raw = data.get("positions")
        positions: list[tuple[str, str, str]] = []
        if isinstance(positions_raw, list):
            items: list[object] = positions_raw
            for pos in items:
                pmap = _object_map_or_empty(pos)
                positions.append(
                    (
                        _opt_str(pmap, "stance"),
                        _opt_str(pmap, "grade"),
                        _opt_str(pmap, "note"),
                    )
                )
        return cls(topic=_req_str(data, "topic", ctx), positions=tuple(positions))

    def render(self) -> str:
        lines = [f"- **{self.topic}**"]
        for stance, grade, note in self.positions:
            grade_str = f" _(GRADE {grade})_" if grade else ""
            note_str = f" — {note}" if note else ""
            lines.append(f"  - {stance}{grade_str}{note_str}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class RetrieverReport:
    """One retriever's claims for a single sub-question."""

    sub_question: str
    question: str
    date: str
    claims: tuple[Claim, ...]
    summary: str

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        ctx = "retriever report"
        data = _require_object(raw, ctx)
        return cls(
            sub_question=_req_str(data, "sub_question", ctx),
            question=_opt_str(data, "question"),
            date=_opt_str(data, "date"),
            claims=_parse_claims(data.get("claims"), ctx),
            summary=_req_str(data, "summary", ctx),
        )


@dataclass(frozen=True, slots=True)
class ResearchReport:
    """The final, two-gate-verified report the adjudicator emits."""

    question: str
    date: str
    author: str
    mode: Mode
    disclaimer: str
    executive_summary: str
    claims: tuple[Claim, ...]
    hypotheses: tuple[Hypothesis, ...]
    contested: tuple[ContestedTopic, ...]
    safety_flags: tuple[SafetyFlag, ...]
    open_questions: tuple[str, ...]
    audit: Mapping[str, object]

    @classmethod
    def from_json(cls: type[Self], raw: object) -> Self:
        ctx = "research report"
        data = _require_object(raw, ctx)
        mode = _parse_enum(Mode, data.get("mode"), "mode", ctx)
        # Safety rail enforced in code: a report with no disclaimer never renders.
        disclaimer = _req_str(data, "disclaimer", ctx)
        hypotheses = _parse_hypotheses(data.get("hypotheses"), ctx)
        if mode is Mode.GROUNDED and hypotheses:
            raise ContractError(
                f"{ctx}: grounded mode must not carry hypotheses[]; "
                "set mode to 'hypothesis' or move them out"
            )
        audit_raw = data.get("audit")
        audit = audit_raw if isinstance(audit_raw, dict) else {}
        return cls(
            question=_req_str(data, "question", ctx),
            date=_opt_str(data, "date"),
            author=_opt_str(data, "author"),
            mode=mode,
            disclaimer=disclaimer,
            executive_summary=_req_str(data, "executive_summary", ctx),
            claims=_parse_claims(data.get("claims"), ctx),
            hypotheses=hypotheses,
            contested=_parse_contested(data.get("contested")),
            safety_flags=_parse_safety_flags(data.get("safety_flags")),
            open_questions=_parse_str_list(data.get("open_questions")),
            audit=audit,
        )


# -- parsing (the only place untyped JSON is touched) -----------------------


def _is_int(value: object) -> TypeGuard[int]:
    # bool subclasses int; a confidence of `True` is a bug, not a number.
    return isinstance(value, int) and not isinstance(value, bool)


def _coerce_int(value: object) -> int | None:
    if _is_int(value):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _require_object(raw: object, ctx: str) -> dict[str, object]:
    if isinstance(raw, dict):
        data: dict[str, object] = raw
        return data
    raise ContractError(f"{ctx}: must be a JSON object")


def _object_map_or_empty(raw: object) -> dict[str, object]:
    if isinstance(raw, dict):
        data: dict[str, object] = raw
        return data
    return {}


def _req_str(data: Mapping[str, object], key: str, ctx: str) -> str:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ContractError(f"{ctx}: missing {key}")
    if not isinstance(value, str):
        raise ContractError(f"{ctx}: {key} must be a string")
    return value


def _opt_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if value is None:
        return ""
    return str(value)


def _opt_bool(data: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = data.get(key)
    if value is None:
        return default
    return bool(value)


def _parse_confidence(value: object, ctx: str) -> int:
    confidence = _coerce_int(value)
    if confidence is None:
        raise ContractError(f"{ctx}: missing confidence (int 0..100)")
    if not 0 <= confidence <= 100:
        raise ContractError(f"{ctx}: confidence must be 0..100, got {confidence}")
    return confidence


_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _parse_enum(enum_cls: type[_EnumT], value: object, field: str, ctx: str) -> _EnumT:
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    valid = tuple(member.value for member in enum_cls)
    raise ContractError(f"{ctx}: {field} must be one of {valid}, got {value!r}")


def _parse_enum_default(
    enum_cls: type[_EnumT], value: object, fallback: _EnumT, field: str, ctx: str
) -> _EnumT:
    if value is None:
        return fallback
    return _parse_enum(enum_cls, value, field, ctx)


def _parse_citations(value: object, ctx: str) -> tuple[Citation, ...]:
    if not isinstance(value, list):
        raise ContractError(f"{ctx}: citations must be a list")
    items: list[object] = value
    return tuple(
        Citation.from_json(item, f"{ctx}.citation[{i}]") for i, item in enumerate(items)
    )


def _parse_claims(value: object, ctx: str) -> tuple[Claim, ...]:
    if not isinstance(value, list):
        raise ContractError(f"{ctx}: claims must be a list")
    items: list[object] = value
    return tuple(Claim.from_json(item, idx) for idx, item in enumerate(items))


def _parse_chain(value: object, ctx: str, n_citations: int) -> tuple[ChainEdge, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{ctx}: chain must be a non-empty list of edges")
    items: list[object] = value
    return tuple(
        ChainEdge.from_json(item, f"{ctx}.chain[{i}]", n_citations)
        for i, item in enumerate(items)
    )


def _parse_hypotheses(value: object, ctx: str) -> tuple[Hypothesis, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ContractError(f"{ctx}: hypotheses must be a list")
    items: list[object] = value
    return tuple(Hypothesis.from_json(item, idx) for idx, item in enumerate(items))


def _parse_contested(value: object) -> tuple[ContestedTopic, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(ContestedTopic.from_json(item, idx) for idx, item in enumerate(items))


def _parse_safety_flags(value: object) -> tuple[SafetyFlag, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(SafetyFlag.from_json(item, idx) for idx, item in enumerate(items))


def _parse_str_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[object] = value
    return tuple(str(item) for item in items if str(item).strip())


# -- rendering --------------------------------------------------------------


def _group_by_sub_question(claims: tuple[Claim, ...]) -> list[tuple[str, list[Claim]]]:
    """Group claims by sub-question, preserving first-seen order."""
    order: list[str] = []
    buckets: dict[str, list[Claim]] = {}
    for claim in claims:
        if claim.sub_question not in buckets:
            buckets[claim.sub_question] = []
            order.append(claim.sub_question)
        buckets[claim.sub_question].append(claim)
    return [(sq, buckets[sq]) for sq in order]


def _tier_counts(claims: tuple[Claim, ...]) -> dict[Tier, int]:
    counts = {tier: 0 for tier in Tier}
    for claim in claims:
        counts[claim.tier] += 1
    return counts


def render_notes(report: RetrieverReport) -> str:
    front = [
        "---",
        f"sub_question: {report.sub_question}",
        f"date: {report.date}",
        f"claims: {len(report.claims)}",
        "---",
    ]
    body = (
        "\n\n".join(c.render() for c in report.claims)
        if report.claims
        else "_No citable evidence found for this sub-question._"
    )
    return "\n".join(
        [
            *front,
            "",
            f"# Retriever Notes — {report.sub_question}",
            "",
            "## Claims",
            "",
            body,
            "",
            "## Summary",
            "",
            report.summary,
            "",
        ]
    )


def _render_claims_section(claims: tuple[Claim, ...]) -> str:
    if not claims:
        return "_No grounded claims survived verification._"
    blocks: list[str] = []
    for sub_question, group in _group_by_sub_question(claims):
        rows = "\n\n".join(c.render() for c in group)
        blocks.append(f"### {sub_question}\n\n{rows}")
    return "\n\n".join(blocks)


def _render_hypotheses_section(hypotheses: tuple[Hypothesis, ...]) -> str:
    if not hypotheses:
        return "_None._"
    return "\n\n".join(h.render() for h in hypotheses)


def _render_list_section(items: tuple[str, ...]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _render_sources(claims: tuple[Claim, ...], hyps: tuple[Hypothesis, ...]) -> str:
    seen: dict[str, Citation] = {}
    for claim in claims:
        for cit in claim.citations:
            seen.setdefault(cit.identifier, cit)
    for hyp in hyps:
        for cit in hyp.citations:
            seen.setdefault(cit.identifier, cit)
    if not seen:
        return "_None._"
    lines: list[str] = []
    for cit in seen.values():
        flag = " ⚠️RETRACTED" if cit.retracted else ""
        if not cit.peer_reviewed:
            flag += " (not peer-reviewed)"
        lines.append(f"- [{cit.identifier}]({cit.url}){flag}")
    return "\n".join(lines)


def _render_audit(audit: Mapping[str, object]) -> str:
    if not audit:
        return "_No audit metadata supplied._"
    keys = ("sub_questions", "searches", "claims_dropped", "refusal_rate", "caveats")
    lines: list[str] = []
    for key in keys:
        if key not in audit:
            continue
        value = audit[key]
        if isinstance(value, list):
            value_items: list[object] = value
            rendered = "; ".join(str(v) for v in value_items)
        else:
            rendered = str(value)
        lines.append(f"- **{key.replace('_', ' ')}**: {rendered}")
    return "\n".join(lines) if lines else "_No audit metadata supplied._"


def render_report(report: ResearchReport) -> str:
    counts = _tier_counts(report.claims)
    front = [
        "---",
        f"question: {report.question}",
        f"date: {report.date}",
        f"author: {report.author}",
        f"mode: {report.mode.value}",
        f"established: {counts[Tier.ESTABLISHED]}",
        f"emerging: {counts[Tier.EMERGING]}",
        f"contested: {counts[Tier.CONTESTED]}",
        f"speculative: {counts[Tier.SPECULATIVE]}",
        f"hypotheses: {len(report.hypotheses)}",
        "---",
    ]
    sections = [
        *front,
        "",
        f"# Medical Research — {report.question}",
        "",
        f"> {report.disclaimer}",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "## Findings",
        "",
        _render_claims_section(report.claims),
        "",
        "## Mechanistic Hypotheses",
        "",
        _render_hypotheses_section(report.hypotheses),
        "",
        "## Contested / Conflicting Evidence",
        "",
        _render_contested_section(report.contested),
        "",
        "## Safety Flags",
        "",
        _render_safety_section(report.safety_flags),
        "",
        "## Open Questions",
        "",
        _render_list_section(report.open_questions),
        "",
        "## Sources",
        "",
        _render_sources(report.claims, report.hypotheses),
        "",
        "## Method / Audit",
        "",
        _render_audit(report.audit),
        "",
    ]
    return "\n".join(sections)


def _render_contested_section(topics: tuple[ContestedTopic, ...]) -> str:
    if not topics:
        return "_None._"
    return "\n\n".join(t.render() for t in topics)


def _render_safety_section(flags: tuple[SafetyFlag, ...]) -> str:
    if not flags:
        return "_None surfaced._"
    return "\n".join(f.render() for f in flags)


# -- CLI --------------------------------------------------------------------

SCHEMA_DOC: Final = __doc__


def _out_path(json_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return json_path.with_suffix(".md")


def _render_cli(kind: str, json_path: str, out: str | None) -> int:
    path = Path(json_path)
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"error": f"file not found: {json_path}"}), file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"error": f"invalid JSON in {json_path}: {exc}"}),
            file=sys.stderr,
        )
        return 2

    try:
        if kind == "notes":
            md = render_notes(RetrieverReport.from_json(raw))
        else:
            md = render_report(ResearchReport.from_json(raw))
    except ContractError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    out_path = _out_path(path, out)
    out_path.write_text(md, encoding="utf-8")
    print(json.dumps({"rendered": str(out_path)}))
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(SCHEMA_DOC)
        return 0 if args else 2
    if args[0] == "--schema":
        print(SCHEMA_DOC)
        return 0
    if args[0] in ("notes", "report"):
        kind = args[0]
        rest = args[1:]
        if not rest:
            print(
                json.dumps({"error": f"usage: schema.py {kind} <json> [out.md]"}),
                file=sys.stderr,
            )
            return 2
        out = rest[1] if len(rest) > 1 else None
        return _render_cli(kind, rest[0], out)
    unknown = f"unknown command {args[0]!r}; expected notes|report|--schema"
    print(json.dumps({"error": unknown}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
