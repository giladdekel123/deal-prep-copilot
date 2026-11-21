"""C1 (owner-approved 2026-11-17): one way to read the numbers written in evidence and in briefings.

The defect it corrects (v2 evaluation, ../../eval/real_companies_v2/ADJUDICATION.md): the briefing side read a figure
with one separator group only ("1,569.7" became 1,569) while the evidence side read 1569.7, so a correct figure was
reported as appearing in no evidence and the repair removed it.

Rules (general: no company, figure or source is treated specially):
- A numeric literal is digits with "," or "." between digit groups. It is not part of a word or identifier ("Q3",
  "FY26", "1H27", "9M" are not figures) and never ends in a separator (a sentence's full stop is not a decimal point).
  A scale written against it ("68m", "2.5bn") or a multiple ("1.5x") is read as its suffix.
- Two number styles exist: English ("1,569.7": comma between thousands, point before decimals) and continental
  ("1.569,7"). A literal that only one style can read, or that both read the same way, is unambiguous ("1,569.7",
  "20.2", "12,345,678", "85").
- A literal the two styles read differently ("1,569" = 1569 or 1.569; "1.569"; "6,2") is read with the style of its
  source: the text it is written in, else the other texts of its source document (the caller passes them). A literal
  whose only reading contradicts that style is kept but marked ambiguous.
- Without any context, an ambiguous literal keeps every reading and is marked ambiguous: it is never silently
  normalized to one value.
- A minus sign directly before a figure ("-0.7", "−0.7") makes it negative; a hyphen between numbers ("2025-26") does
  not.
"""
import re
from dataclasses import dataclass

# A literal (group 'num') with an optional attached scale or multiple (group 'suffix'). The lookbehind keeps it from
# starting inside a word, identifier or longer number; the lookahead keeps it from stopping inside one.
TOKEN = re.compile(r"(?<![\w.,])(?<!\d:)(?P<num>\d+(?:[.,]\d+)*)(?P<suffix>bn|mn|m|k|x)?(?![\w]|[.,:]\d)")
# (digits joined by a colon are a time or a ratio, "07:30", "3:1": not figures)
_EN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_EU = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
SCALE = {"bn": 1e9, "billion": 1e9, "b": 1e9, "mn": 1e6, "m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}
# The words after a figure that name a count of whole things (at most two words between: "4,250 full-time
# employees"). A scale word right after the figure makes it an amount, not a count ("1,569 million people").
_COUNT = re.compile(r"^\s*(?!(?:million|billion|thousand|bn|mn|m)\b)(?:[A-Za-z-]+\s+){0,2}?(?:people|persons|"
                    r"employees|staff|workers|colleagues|users|customers|clients|subscribers|members|patients|students|"
                    r"passengers|stores|shops|outlets|sites|offices|branches|countries|cities|locations|aircraft|"
                    r"planes|vessels|ships|vehicles|units|shares|seats|licen[cs]es|beds|homes|projects|contracts|"
                    r"hospitals|centres|centers|plants|turbines|factories)\b", re.I)
_SIGN = "-−–"
_YEAR = re.compile(r"(?:19|20)\d{2}")


@dataclass(frozen=True)
class Number:
    literal: str                       # the digits and separators as written (no sign, no suffix)
    start: int                         # span of the literal in the text
    end: int
    negative: bool
    suffix: str                        # an attached scale or multiple ("m", "bn", "x"), else ""
    readings: tuple                    # ((value, decimals), ...): one when unambiguous; signed
    ambiguous: bool
    style: str | None                  # the style that decided the reading ("en", "eu"), or None

    @property
    def values(self) -> tuple:
        return tuple(v for v, _ in self.readings)


def _reading(literal: str, style: str) -> tuple | None:
    """(value, decimals) of a literal in one style, or None when that style cannot read it."""
    pattern, group, point = (_EN, ",", ".") if style == "en" else (_EU, ".", ",")
    if not pattern.fullmatch(literal):
        return None
    whole, _, frac = literal.replace(group, "").partition(point)
    return float(f"{whole}.{frac}" if frac else whole), len(frac)


def styles(literal: str) -> dict:
    """{style: (value, decimals)} for every style that can read the literal."""
    return {s: r for s in ("en", "eu") if (r := _reading(literal, s)) is not None}


def style_of(texts) -> str | None:
    """The number style a set of texts shows: 'en' or 'eu' when their literals that only one style can read all use
    that style, 'mixed' when both occur, None when no literal shows a style (ambiguous literals show none)."""
    seen = set()
    for text in ([texts] if isinstance(texts, str) else texts):
        for m in TOKEN.finditer(text or ""):
            r = styles(m.group("num"))
            if len(r) == 1:
                seen.add(next(iter(r)))
    return next(iter(seen)) if len(seen) == 1 else "mixed" if seen else None


def interpret(literal: str, style: str | None = None, negative: bool = False) -> tuple:
    """(readings, ambiguous, deciding style) of a literal given its source's style ('en', 'eu', 'mixed' or None)."""
    r = styles(literal)
    sign = -1.0 if negative else 1.0
    signed = lambda x: (sign * x[0], x[1])  # noqa: E731
    if not r:
        return (), False, None
    values = {v for v in r.values()}
    if len(values) == 1:  # one style, or both reading it the same way
        only = next(iter(r)) if len(r) == 1 else None
        contradicted = only is not None and style is not None and style != only  # the source uses the other style
        return (signed(next(iter(values))),), contradicted, only
    if style in r:  # the styles disagree: the source's own style decides
        return (signed(r[style]),), False, style
    return tuple(signed(x) for x in sorted(set(r.values()))), True, None


def counted(readings: tuple, following: str) -> tuple:
    """A count of whole things is a whole number: of an ambiguous literal's readings, keep the one whole reading when
    the words after the figure name what is counted ("4,250 employees" is 4250, never 4.25)."""
    if len(readings) > 1 and _COUNT.match(following or ""):
        whole = tuple(r for r in readings if r[1] == 0)
        if len(whole) == 1:
            return whole
    return readings


def read(text: str, context=()) -> list[Number]:
    """Every numeric literal of a text, read with the text's own style, else the style of `context` (the other texts
    of its source)."""
    text = text or ""
    style = style_of(text) or (style_of(context) if context else None)
    out = []
    for m in TOKEN.finditer(text):
        start = m.start("num")
        before = text[start - 1] if start else ""
        before2 = text[start - 2] if start > 1 else ""
        negative = bool(before) and before in _SIGN and not before2.isalnum()
        readings, ambiguous, decided = interpret(m.group("num"), style, negative)
        if not readings:
            continue  # malformed ("21.10.2026", "1,5,6"): not a figure
        if len(readings) > 1:  # the words after it may settle it: a count is whole
            whole = counted(readings, text[m.end():m.end() + 60])
            if len(whole) == 1:
                readings, ambiguous, decided = whole, False, "count"
        out.append(Number(m.group("num"), start, m.end("num"), negative, m.group("suffix") or "", readings,
                          ambiguous, decided or style))
    return out


def values(text: str, context=()) -> set[float]:
    """Every value the numbers of a text can have (all readings of an ambiguous literal), with attached scales applied
    as alternatives (68m is 68 and 68,000,000)."""
    out = set()
    for n in read(text, context):
        for v in n.values:
            out.add(v)
            if n.suffix in SCALE:
                out.add(v * SCALE[n.suffix])
    return out


def is_year(literal: str) -> bool:
    return bool(_YEAR.fullmatch(literal))


def marker(literal: str, style: str | None = None) -> str:
    """A pattern for the same figure in a briefing: the literal as written, and, when its value is certain, the same
    value with or without thousands separators ("1,569.7" or "1569.7"). An ambiguous literal matches only itself."""
    readings, ambiguous, _ = interpret(literal, style)
    forms = [re.escape(literal)]
    if readings and not ambiguous and len(readings) == 1:
        value, decimals = readings[0]
        whole, _, frac = f"{abs(value):.{decimals}f}".partition(".")
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        forms.append(",?".join(groups) + (rf"\.{frac}" if frac else ""))
    return rf"(?<![\d.,])(?:{'|'.join(dict.fromkeys(forms))})(?![\d]|[.,]\d)"
