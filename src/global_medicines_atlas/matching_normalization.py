"""Reversible, Unicode-aware normalization for deterministic matching."""

from __future__ import annotations

import re
import unicodedata

from pydantic import Field

from .models import FrozenModel

_TOKEN_RE = re.compile(r"\w+(?:[.,]\w+)*", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


class NormalizedText(FrozenModel):
    """A normalized view that always retains the unmodified source value."""

    source: str = Field(min_length=1)
    unicode_text: str = Field(min_length=1)
    comparison_text: str = Field(min_length=1)
    tokens: tuple[str, ...] = Field(min_length=1)


class MatchingFeatures(FrozenModel):
    """Explicit medicine attributes; no attribute is discarded into a name."""

    name: NormalizedText
    ingredients: tuple[NormalizedText, ...] = ()
    strength_value: str | None = None
    strength_unit: str | None = None
    dose_form: NormalizedText | None = None
    route: NormalizedText | None = None


def _comparison_key(value: NormalizedText) -> tuple[str, str, str]:
    """Order normalized collisions without retaining source input order."""

    return (value.comparison_text, value.unicode_text, value.source)


def normalize_text(value: str) -> NormalizedText:
    """Create a deterministic comparison view while preserving ``value``."""

    if not value.strip():
        raise ValueError("Matching text must not be blank")
    unicode_text = unicodedata.normalize("NFKC", value)
    casefolded = _SPACE_RE.sub(" ", unicode_text.casefold()).strip()
    tokens = tuple(_TOKEN_RE.findall(casefolded))
    if not tokens:
        raise ValueError("Matching text must contain a Unicode word")
    return NormalizedText(
        source=value,
        unicode_text=unicode_text,
        comparison_text=" ".join(tokens),
        tokens=tokens,
    )


def normalize_unit(value: str | None) -> str | None:
    if value is None:
        return None
    aliases = {
        "milligram": "mg",
        "milligrams": "mg",
        "microgram": "μg",
        "micrograms": "μg",
        "mcg": "μg",
        "μg": "μg",
        "millilitre": "ml",
        "millilitres": "ml",
    }
    normalized = normalize_text(value).comparison_text
    return aliases.get(normalized, normalized)


def normalize_strength(value: str | int | float | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return normalize_text(text).comparison_text
    return format(number, ".12g")


def build_features(
    *,
    name: str,
    ingredients: tuple[str, ...] = (),
    strength_value: str | int | float | None = None,
    strength_unit: str | None = None,
    dose_form: str | None = None,
    route: str | None = None,
) -> MatchingFeatures:
    normalized_ingredients: list[NormalizedText] = [
        normalize_text(value) for value in ingredients
    ]
    return MatchingFeatures(
        name=normalize_text(name),
        ingredients=tuple(sorted(normalized_ingredients, key=_comparison_key)),
        strength_value=normalize_strength(strength_value),
        strength_unit=normalize_unit(strength_unit),
        dose_form=normalize_text(dose_form) if dose_form else None,
        route=normalize_text(route) if route else None,
    )
