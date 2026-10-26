"""Classify free-text privacy requests.

A deletion workflow must never act on a request that only asks for access,
correction, export, marketing opt-out, or restriction. Classification is
deliberately conservative: an explicit, non-negated deletion verb is required.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DELETION = "DELETION"
DELETE = DELETION
ACCESS = "ACCESS"
CORRECTION = "CORRECTION"
EXPORT = "EXPORT"
OPT_OUT = "OPT_OUT"
RESTRICTION = "RESTRICTION"
UNKNOWN = "UNKNOWN"

_DELETION_TERMS = (
    r"\b(?:delete|deletion|erase|erasure|purge|wipe|destroy)\b",
    r"\bremove\s+(?:all\s+)?(?:my|the)\b",
    r"\bright\s+to\s+be\s+forgotten\b",
    r"\bforget\s+(?:me|my)\b",
    r"\b(?:close|cancel|deactivate)\s+my\s+account\b",
    r"\bget\s+rid\s+of\s+my\b",
    r"\bno\s+longer\s+want\s+(?:my|you\s+to\s+keep)\b",
    r"\bnot\s+want\s+my\s+data\b",
    r"\beliminar\b",
    r"\bborrar\b",
    r"\bsuprimir\b",
    r"\bderecho\s+al\s+olvido\b",
    r"\bolvidar\b",
    r"\bdar\s+de\s+baja\b",
    r"\bsupprimer\b",
    r"\beffacer\b",
    r"\bdroit\s+[àa]\s+l'oubli\b",
    r"\boublier\b",
    r"\bl[öo]schen\b",
    r"\bentfernen\b",
    r"\brecht\s+auf\s+vergessen\b",
    r"\bvergessen\b",
    r"\bexcluir\b",
    r"\bapagar\b",
    r"\bapague(?:m)?\b",
    r"\bexclua(?:m)?\b",
    r"\belimine(?:m)?\b",
    r"\besquecer\b",
    r"\bdireito\s+ao\s+esquecimento\b",
    r"\bcancellare\b",
    r"\beliminare\b",
    r"\bdimenticare\b",
    r"\bdiritto\s+all'oblio\b",
    r"\bverwijderen\b",
    r"\bwissen\b",
    r"(?:मिटा|हटा|भूल|डिलीट)",
)

_OTHER_TERMS: dict[str, tuple[str, ...]] = {
    ACCESS: (
        r"\b(?:access|see|view|list)\s+(?:my|the)\s+(?:data|information|records)\b",
        r"\bright\s+of\s+access\b",
        r"\bsubject\s+access\s+request\b",
        r"\bwhat\s+data\s+do\s+you\s+(?:have|hold)\b",
        r"\bwhat\s+(?:personal\s+)?data\s+you\s+(?:have|hold|store)\b",
        r"\bshow\s+me\s+(?:what|the)\s+data\b",
        r"\bacceso\s+a\s+mis\s+datos\b",
        r"\bc[óo]pia\s+dos?\s+meus\s+dados\b",
        r"\bacc[èe]s\s+[àa]\s+mes\s+donn[ée]es\b",
        r"\bacc[ée]der\s+[àa]\s+(?:mes|aux)\s+donn[ée]es\b",
        r"\bauskunft\b",
        r"\baccesso\s+ai\s+miei\s+dati\b",
    ),
    EXPORT: (
        r"\bexport\s+(?:my|all|the)\b",
        r"\bdownload\s+(?:my|a\s+copy)\b",
        r"\bsend\s+me\s+(?:a\s+)?copy\b",
        r"\bcopy\s+of\s+my\s+(?:data|information|records)\b",
        r"\bcopia\s+de\s+(?:mis|meus|mes)\s+(?:datos|dados|donn[ée]es)\b",
        r"\bdata\s+portability\b",
        r"\bportabilidad\b",
        r"\bportabilit[ée]\b",
        r"\bdaten[üu]bertragbarkeit\b",
        r"\bportabilidade\b",
        r"\bportabilit[àa]\b",
    ),
    CORRECTION: (
        r"\b(?:correct|fix|rectify)\s+my\b",
        r"\b(?:update|change)\s+my\s+(?:email|phone|name|address|details)\b",
        r"\bmy\s+(?:email|phone|name)\s+is\s+(?:wrong|incorrect)\b",
        r"\brectification\b",
        r"\bcorregir\b",
        r"\bactualizar\b",
        r"\brectificar\b",
        r"\bcorriger\b",
        r"\brectifier\b",
        r"\bmettre\s+[àa]\s+jour\b",
        r"\bberichtigen\b",
        r"\bkorrigieren\b",
        r"\baktualisieren\b",
        r"\bcorrigir\b",
        r"\batualizar\b",
        r"\bcorreggere\b",
        r"\baggiornare\b",
    ),
    OPT_OUT: (
        r"\bunsubscribe\b",
        r"\bstop\s+(?:emailing|sending\s+me|contacting\s+me)\b",
        r"\bopt\s+out\b",
        r"\bmarketing\s+(?:emails?|preferences?)\b",
        r"\bnewsletter\b",
        r"\bdarse\s+de\s+baja\b",
        r"\bse\s+d[ée]sabonner\b",
        r"\babmelden\b",
        r"\bdescadastrar\b",
        r"\bannullare\s+l'iscrizione\b",
    ),
    RESTRICTION: (
        r"\brestrict\s+(?:the\s+)?processing\b",
        r"\bstop\s+processing\b",
        r"\bobject\s+to\s+(?:the\s+)?processing\b",
        r"\blimitar\s+el\s+tratamiento\b",
        r"\bwiderspruch\b",
        r"\bopposition\b",
        r"\boposi[çc][ãa]o\b",
    ),
}

_NEGATED_DELETION = (
    r"\b(?:do\s+not|don'?t|dont|never|please\s+do\s+not|please\s+don'?t)\s+"
    r"(?:delete|erase|remove|purge|wipe)\b",
    r"\b(?:do\s+not|don'?t|dont)\s+want\s+(?:to\s+)?(?:delete|erase|remove)\b",
    r"\b(?:not|n't)\s+(?:ready|wish)\s+to\s+(?:delete|erase|remove)\b",
    r"\bno\s+(?:eliminar|borrar|suprimir)\b",
    r"\bne\s+(?:supprimez|effacez)\s+pas\b",
    r"\bnicht\s+(?:l[öo]schen|entfernen)\b",
    r"\bn[ãa]o\s+(?:apague|exclua|elimine)\b",
    r"\bnon\s+(?:cancellare|eliminare)\b",
)

_DELETION_RE = tuple(re.compile(p, re.IGNORECASE) for p in _DELETION_TERMS)
_OTHER_RE = {
    category: tuple(re.compile(p, re.IGNORECASE) for p in patterns)
    for category, patterns in _OTHER_TERMS.items()
}
_NEGATED_RE = tuple(re.compile(p, re.IGNORECASE) for p in _NEGATED_DELETION)


@dataclass(frozen=True, slots=True)
class RequestIntent:
    is_deletion: bool
    category: str
    confidence: float
    reason: str
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "is_deletion": self.is_deletion,
            "category": self.category,
            "confidence": self.confidence,
            "reason": self.reason,
            "matched_terms": list(self.matched_terms),
        }


def _matches(patterns, text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            hits.append(match.group(0).strip().lower())
    return hits


def _is_negated(sentence: str) -> bool:
    return any(pattern.search(sentence) for pattern in _NEGATED_RE)


def classify_request(text: str) -> RequestIntent:
    if not text or not text.strip():
        return RequestIntent(False, UNKNOWN, 0.2, "empty request")

    normalized = unicodedata.normalize("NFKC", text).lower()
    sentences = [s for s in re.split(r"[.!?;\n]+", normalized) if s.strip()]

    deletion_hits: list[str] = []
    other_hits: dict[str, list[str]] = {}

    for sentence in sentences:
        if _is_negated(sentence):
            continue
        deletion_hits.extend(_matches(_DELETION_RE, sentence))
        for category, patterns in _OTHER_RE.items():
            hits = _matches(patterns, sentence)
            if hits:
                other_hits.setdefault(category, []).extend(hits)

    if deletion_hits:
        confidence = 0.95 if not other_hits else 0.8
        reason = "explicit deletion language" if not other_hits else (
            "explicit deletion language alongside another request type"
        )
        return RequestIntent(
            True,
            DELETION,
            confidence,
            reason,
            tuple(sorted(set(deletion_hits))),
        )

    if other_hits:
        category = next(iter(other_hits))
        terms = tuple(sorted({hit for hits in other_hits.values() for hit in hits}))
        return RequestIntent(
            False,
            category,
            0.9,
            f"request asks for {category.lower()}, not deletion",
            terms,
        )

    return RequestIntent(False, UNKNOWN, 0.4, "no explicit deletion language", ())
