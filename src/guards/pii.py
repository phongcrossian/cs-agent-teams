"""
PII redaction using Microsoft Presidio (D-12).

RULE (CLAUDE.md / D-12): Call redact_text() BEFORE any log statement, DB persist,
or trace that contains ticket body / customer content.  Never log raw ticket text.

Entities redacted:
  PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN, LOCATION,
  IP_ADDRESS, URL

spaCy model required: en_core_web_lg
  Install: python -m spacy download en_core_web_lg
  (Pitfall 5 from RESEARCH: AnalyzerEngine() will raise OSError if model missing)

Singleton pattern: AnalyzerEngine + AnonymizerEngine are initialised once
on first call (lazy) because loading the spaCy model is expensive (~1s).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine as _AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine as _AnonymizerEngine

# Entities to detect and redact
_REDACT_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "LOCATION",
    "IP_ADDRESS",
    "URL",
]

# Lazy singletons — populated on first call to redact_text()
_analyzer: "_AnalyzerEngine | None" = None
_anonymizer: "_AnonymizerEngine | None" = None


def _get_engines() -> "tuple[_AnalyzerEngine, _AnonymizerEngine]":
    """Return (analyzer, anonymizer) singletons, initialising them on first call."""
    global _analyzer, _anonymizer
    if _analyzer is None or _anonymizer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def redact_text(text: str) -> str:
    """Replace PII in *text* with entity-type tags (e.g. <EMAIL_ADDRESS>).

    Returns the redacted string.  Empty / whitespace-only strings are returned
    as-is without calling Presidio (no-op — avoids unnecessary model invocation).

    Usage:
        body_safe = redact_text(conv.body_text)
        logger.info("processing", ticket_id=ticket_id, body_preview=body_safe[:100])

    Security contract (D-12):
        This function MUST be called before any log or DB write that contains
        customer-supplied content.  The caller is responsible for passing the
        full text; partial redaction is NOT acceptable.
    """
    if not text or not text.strip():
        return text

    analyzer, anonymizer = _get_engines()

    results = analyzer.analyze(
        text=text,
        entities=_REDACT_ENTITIES,
        language="en",
    )
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text
