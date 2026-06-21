"""Core fact-checking pipeline for the Streamlit app.

The implementation intentionally avoids mandatory LLM/API dependencies. It
extracts quantified claims from uploaded PDFs, searches the live web, and scores
each claim against source snippets using quantity and keyword agreement.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence
from urllib.parse import urlparse


STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "among",
    "because",
    "been",
    "before",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "more",
    "most",
    "over",
    "that",
    "their",
    "than",
    "then",
    "there",
    "these",
    "this",
    "through",
    "under",
    "using",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RE = re.compile(rf"\b{MONTH_RE}\s+\d{{1,2}},?\s+\d{{4}}\b|\b\d{{1,2}}\s+{MONTH_RE}\s+\d{{4}}\b", re.I)
NUMERIC_SIGNAL_RE = re.compile(
    r"(?:[$€£₹]\s*)?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*"
    r"(?:percentage points?|percent|%|basis points|bps|times|x|"
    r"trillion|tn|t|billion|bn|b|million|mn|m|thousand|k|crore|lakh|"
    r"users?|customers?|people|queries|prompts?|countries|languages|"
    r"revenue|arr|mrr)?\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
QUANTITY_RE = re.compile(
    r"(?P<prefix>[$€£₹])?\s*"
    r"(?P<number>\d{1,3}(?:,\d{3})+|\d+)(?P<decimal>\.\d+)?\s*"
    r"(?P<unit>percentage points?|percent|%|basis points|bps|times|x|"
    r"trillion|tn|t|billion|bn|b|million|mn|m|thousand|k|crore|lakh)?",
    re.I,
)


@dataclass(frozen=True)
class Quantity:
    raw: str
    value: float
    kind: str
    unit: str


@dataclass(frozen=True)
class Evidence:
    title: str
    url: str
    snippet: str

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.replace("www.", "")


@dataclass(frozen=True)
class ClaimReport:
    claim: str
    status: str
    confidence: float
    correction: str
    query: str
    matched_quantities: list[str]
    alternative_quantities: list[str]
    evidence: list[Evidence]

    def to_row(self) -> dict[str, str | float]:
        primary = self.evidence[0] if self.evidence else None
        return {
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "claim": self.claim,
            "correction": self.correction,
            "top_source": primary.domain if primary else "",
            "top_url": primary.url if primary else "",
        }


SearchFunction = Callable[[str, int], Sequence[Evidence]]


def extract_pdf_text(file_or_path: str | Path | bytes | io.BytesIO) -> str:
    """Extract text from a PDF path, bytes object, or Streamlit UploadedFile."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency message
        raise RuntimeError("pypdf is required to extract PDF text") from exc

    if isinstance(file_or_path, (str, Path)):
        reader = PdfReader(str(file_or_path))
    else:
        if hasattr(file_or_path, "getvalue"):
            data = file_or_path.getvalue()
        elif isinstance(file_or_path, bytes):
            data = file_or_path
        else:
            data = file_or_path.read()
        reader = PdfReader(io.BytesIO(data))

    page_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page_text).strip()


def extract_candidate_claims(text: str, max_claims: int = 12) -> list[str]:
    """Return quantified factual claims likely to need verification."""

    sentences = _split_sentences(text)
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for idx, sentence in enumerate(sentences):
        sentence = _clean_sentence(sentence)
        if not (35 <= len(sentence) <= 320):
            continue
        if not _has_claim_signal(sentence):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        scored.append((_claim_score(sentence), idx, sentence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [sentence for _, _, sentence in scored[:max_claims]]


def verify_claim(
    claim: str,
    search_func: SearchFunction | None = None,
    max_results: int = 6,
) -> ClaimReport:
    """Search the web and classify a claim.

    Search/network failures are separated from false claims so the app does not
    punish a document when live search is unavailable.
    """

    search = search_func or search_web
    query = build_search_query(claim)
    try:
        evidence = list(search(query, max_results))
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        evidence = []
        search_error = str(exc)
    else:
        search_error = ""

    if not evidence:
        if search_error:
            correction = f"Live search was unavailable: {search_error}"
            return ClaimReport(claim, "Search unavailable", 0.0, correction, query, [], [], [])
        correction = "No matching evidence was returned by live search."
        return ClaimReport(claim, "False", 0.35, correction, query, [], [], [])

    evidence_text = " ".join(
        f"{item.title}. {item.snippet}" for item in evidence if item.title or item.snippet
    )
    claim_quantities = parse_quantities(claim)
    evidence_quantities = parse_quantities(evidence_text)
    matches = _matched_quantities(claim_quantities, evidence_quantities)
    alternatives = _alternative_quantities(claim_quantities, evidence_quantities)
    relevance = max(_relevance_score(claim, f"{item.title} {item.snippet}") for item in evidence)

    if claim_quantities:
        match_ratio = len(matches) / max(1, len(claim_quantities))
        if match_ratio >= 0.6 and relevance >= 0.08:
            status = "Verified"
            confidence = min(0.95, 0.7 + match_ratio * 0.18 + relevance * 0.25)
            correction = "Top web evidence repeats the key quantity or date in the claim."
        elif relevance >= 0.08 and alternatives:
            status = "Inaccurate"
            confidence = min(0.86, 0.55 + relevance * 0.35 + min(len(alternatives), 3) * 0.05)
            correction = "Related sources point to different figures or dates; review the alternatives and linked evidence."
        else:
            status = "False"
            confidence = min(0.72, 0.42 + relevance * 0.4)
            correction = "Search found weak topical overlap and no corroborating quantity/date."
    elif relevance >= 0.18:
        status = "Verified"
        confidence = min(0.82, 0.55 + relevance * 0.5)
        correction = "Search results are topically aligned with the claim."
    else:
        status = "False"
        confidence = min(0.65, 0.4 + relevance * 0.5)
        correction = "No strong supporting evidence found in the top live-search results."

    return ClaimReport(
        claim=claim,
        status=status,
        confidence=round(confidence, 2),
        correction=correction,
        query=query,
        matched_quantities=[quantity.raw for quantity in matches],
        alternative_quantities=alternatives[:8],
        evidence=evidence,
    )


def fact_check_text(
    text: str,
    max_claims: int = 12,
    max_results: int = 6,
    search_func: SearchFunction | None = None,
) -> list[ClaimReport]:
    claims = extract_candidate_claims(text, max_claims=max_claims)
    return [verify_claim(claim, search_func=search_func, max_results=max_results) for claim in claims]


def search_web(query: str, max_results: int = 6) -> list[Evidence]:
    """Run a DuckDuckGo search and normalize result objects."""

    ddgs_cls = None
    try:
        from ddgs import DDGS as ddgs_cls
    except ImportError:  # pragma: no cover - depends on installed package name
        try:
            from duckduckgo_search import DDGS as ddgs_cls
        except ImportError as exc:
            raise RuntimeError("Install ddgs to enable live search") from exc

    normalized: list[Evidence] = []
    with ddgs_cls() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            title = str(item.get("title") or "").strip()
            url = str(item.get("href") or item.get("url") or "").strip()
            snippet = str(item.get("body") or item.get("snippet") or "").strip()
            if title and url:
                normalized.append(Evidence(title=title, url=url, snippet=snippet))
    return normalized


def build_search_query(claim: str) -> str:
    keywords = [token for token in _tokens(claim) if token not in STOPWORDS]
    numbers = re.findall(r"(?:[$€£₹]\s*)?\d[\d,.]*\s*(?:%|percent|million|billion|trillion|bn|m|k)?", claim, re.I)
    head = " ".join(keywords[:12])
    number_part = " ".join(numbers[:4])
    query = f"{head} {number_part}".strip()
    return query[:220] or claim[:220]


def parse_quantities(text: str) -> list[Quantity]:
    quantities: list[Quantity] = []
    for match in QUANTITY_RE.finditer(text):
        raw = match.group(0).strip()
        if not raw:
            continue
        number = float((match.group("number") + (match.group("decimal") or "")).replace(",", ""))
        unit = (match.group("unit") or "").lower()
        prefix = match.group("prefix") or ""
        kind = "number"

        if unit in {"k", "thousand"}:
            number *= 1_000
            unit = "count"
        elif unit in {"m", "mn", "million"}:
            number *= 1_000_000
            unit = "count"
        elif unit in {"b", "bn", "billion"}:
            number *= 1_000_000_000
            unit = "count"
        elif unit in {"t", "tn", "trillion"}:
            number *= 1_000_000_000_000
            unit = "count"
        elif unit == "crore":
            number *= 10_000_000
            unit = "count"
        elif unit == "lakh":
            number *= 100_000
            unit = "count"

        if unit in {"%", "percent", "percentage point", "percentage points"}:
            kind = "percent"
            unit = "%"
        elif unit in {"bps", "basis point", "basis points"}:
            kind = "basis_points"
            unit = "bps"
        elif unit in {"x", "times"}:
            kind = "multiple"
            unit = "x"
        elif prefix:
            kind = "currency"
            unit = prefix
        elif 1900 <= number <= 2099 and number.is_integer() and not unit:
            kind = "year"
            unit = "year"
        elif unit == "count":
            kind = "count"
        elif not unit:
            unit = "plain"

        quantities.append(Quantity(raw=raw, value=number, kind=kind, unit=unit))
    return _dedupe_quantities(quantities)


def reports_to_csv(reports: Sequence[ClaimReport]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["status", "confidence", "claim", "correction", "top_source", "top_url"],
    )
    writer.writeheader()
    for report in reports:
        writer.writerow(report.to_row())
    return output.getvalue()


def generate_markdown_report(reports: Sequence[ClaimReport]) -> str:
    counts = {
        status: sum(1 for report in reports if report.status == status)
        for status in ("Verified", "Inaccurate", "False", "Search unavailable")
    }
    lines = [
        "# Fact-Check Report",
        "",
        f"Summary: {counts['Verified']} verified, {counts['Inaccurate']} inaccurate, "
        f"{counts['False']} false/no evidence, {counts['Search unavailable']} search unavailable.",
        "",
    ]
    for idx, report in enumerate(reports, start=1):
        lines.extend(
            [
                f"## {idx}. {report.status} ({report.confidence:.2f})",
                "",
                f"Claim: {report.claim}",
                "",
                f"Finding: {report.correction}",
                "",
            ]
        )
        if report.matched_quantities:
            lines.append(f"Matched quantities: {', '.join(report.matched_quantities)}")
            lines.append("")
        if report.alternative_quantities:
            lines.append(f"Alternative figures/dates found: {', '.join(report.alternative_quantities)}")
            lines.append("")
        if report.evidence:
            lines.append("Evidence:")
            for item in report.evidence[:5]:
                lines.append(f"- [{item.title}]({item.url}) - {item.snippet}")
            lines.append("")
    return "\n".join(lines)


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned)
    sentences: list[str] = []
    for part in parts:
        if len(part) > 320:
            sentences.extend(re.split(r"\s*[;]\s*", part))
        else:
            sentences.append(part)
    return sentences


def _clean_sentence(sentence: str) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip(" -")
    return sentence


def _has_claim_signal(sentence: str) -> bool:
    return bool(NUMERIC_SIGNAL_RE.search(sentence) or YEAR_RE.search(sentence) or DATE_RE.search(sentence))


def _claim_score(sentence: str) -> int:
    score = 0
    score += len(NUMERIC_SIGNAL_RE.findall(sentence)) * 3
    score += len(YEAR_RE.findall(sentence)) * 2
    score += len(DATE_RE.findall(sentence)) * 2
    if re.search(r"\b(revenue|market|users|customers|growth|traffic|share|cost|price|profit|loss|launched|founded|raised)\b", sentence, re.I):
        score += 3
    if re.search(r"\b(always|never|only|largest|first|most|least|all|none)\b", sentence, re.I):
        score += 1
    return score


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower()) if token not in STOPWORDS]


def _relevance_score(claim: str, evidence: str) -> float:
    claim_tokens = set(_tokens(claim))
    evidence_tokens = set(_tokens(evidence))
    if not claim_tokens or not evidence_tokens:
        return 0.0
    overlap = claim_tokens & evidence_tokens
    return len(overlap) / math.sqrt(len(claim_tokens) * len(evidence_tokens))


def _matched_quantities(claim_quantities: Sequence[Quantity], evidence_quantities: Sequence[Quantity]) -> list[Quantity]:
    matches: list[Quantity] = []
    for claim_quantity in claim_quantities:
        if any(_quantity_matches(claim_quantity, evidence_quantity) for evidence_quantity in evidence_quantities):
            matches.append(claim_quantity)
    return matches


def _quantity_matches(left: Quantity, right: Quantity) -> bool:
    if left.kind != right.kind:
        return False
    if left.kind == "year":
        return int(left.value) == int(right.value)
    if left.kind in {"percent", "basis_points"}:
        return abs(left.value - right.value) <= max(0.2, abs(left.value) * 0.02)
    if left.value == 0:
        return right.value == 0
    return abs(left.value - right.value) / abs(left.value) <= 0.03


def _alternative_quantities(claim_quantities: Sequence[Quantity], evidence_quantities: Sequence[Quantity]) -> list[str]:
    alternatives: list[str] = []
    claim_kinds = {quantity.kind for quantity in claim_quantities}
    for evidence_quantity in evidence_quantities:
        if evidence_quantity.kind not in claim_kinds:
            continue
        if any(_quantity_matches(claim_quantity, evidence_quantity) for claim_quantity in claim_quantities):
            continue
        if evidence_quantity.raw not in alternatives:
            alternatives.append(evidence_quantity.raw)
    return alternatives


def _dedupe_quantities(quantities: Iterable[Quantity]) -> list[Quantity]:
    deduped: list[Quantity] = []
    seen: set[tuple[str, int, str]] = set()
    for quantity in quantities:
        key = (quantity.kind, round(quantity.value), quantity.unit)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(quantity)
    return deduped


def reports_as_dicts(reports: Sequence[ClaimReport]) -> list[dict]:
    return [asdict(report) for report in reports]
