from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from boiler_reviews.catalog.schema import CatalogDocument


class CatalogAdapterError(ValueError):
    """A source export cannot be converted without guessing its meaning."""


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_uri: str
    source_kind: str
    content_hash: str
    synthetic: bool
    accessed_at: str | None = None
    terms_url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_uri": self.source_uri,
            "source_kind": self.source_kind,
            "content_hash": self.content_hash,
            "synthetic": self.synthetic,
            "accessed_at": self.accessed_at,
            "terms_url": self.terms_url,
        }


class CatalogAdapter(Protocol):
    def read(self, payload: str, *, source_uri: str) -> tuple[CatalogDocument, SourceProvenance]: ...


def provenance_for(payload: str, *, source_uri: str, source_kind: str, synthetic: bool) -> SourceProvenance:
    return SourceProvenance(source_uri, source_kind, hashlib.sha256(payload.encode("utf-8")).hexdigest(), synthetic)


class JsonCatalogAdapter:
    def read(self, payload: str, *, source_uri: str) -> tuple[CatalogDocument, SourceProvenance]:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise CatalogAdapterError(f"catalog JSON is malformed at character {error.pos}") from error
        if not isinstance(value, dict):
            raise CatalogAdapterError("catalog JSON must contain an object")
        value = dict(value)
        value.setdefault("source_uri", source_uri)
        provenance = dict(value.get("provenance", {}))
        provenance.setdefault("source_kind", "canonical_json")
        provenance.setdefault("synthetic", source_uri.startswith("fixture:"))
        value["provenance"] = provenance
        try:
            document = CatalogDocument.model_validate(value)
        except Exception as error:
            raise CatalogAdapterError(f"catalog JSON failed canonical validation: {error}") from error
        return document, provenance_for(payload, source_uri=source_uri, source_kind="canonical_json", synthetic=bool(provenance["synthetic"]))


class CsvCatalogAdapter:
    """Convert a documented flat course export without inventing rules."""

    required_columns = frozenset({"code", "title", "credits"})

    def read(self, payload: str, *, source_uri: str) -> tuple[CatalogDocument, SourceProvenance]:
        reader = csv.DictReader(io.StringIO(payload))
        columns = frozenset(reader.fieldnames or ())
        missing = self.required_columns - columns
        if missing:
            raise CatalogAdapterError(f"catalog CSV is missing columns: {', '.join(sorted(missing))}")
        courses: list[dict[str, Any]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                credits = int((row.get("credits") or "").strip())
            except ValueError as error:
                raise CatalogAdapterError(f"row {row_number}: credits must be an integer") from error
            if not row.get("code") or not row.get("title"):
                raise CatalogAdapterError(f"row {row_number}: code and title are required")
            availability = {}
            raw_availability = (row.get("availability") or "").strip()
            if raw_availability:
                for term in raw_availability.split("|"):
                    term = term.strip()
                    if term:
                        availability[term] = True
            courses.append({
                "code": row["code"].strip().upper(),
                "stable_code": (row.get("stable_code") or row["code"]).strip().upper(),
                "title": row["title"].strip(),
                "credits": credits,
                "description": row.get("description") or None,
                "prerequisites": row.get("prerequisites") or "NONE",
                "availability": availability,
            })
        value = {
            "schema_version": "1",
            "institution_code": "CSV",
            "institution_name": "Imported CSV institution",
            "version": hashlib.sha256(payload.encode()).hexdigest()[:16],
            "source_uri": source_uri,
            "provenance": {"source_kind": "documented_csv", "synthetic": False},
            "courses": courses,
        }
        try:
            document = CatalogDocument.model_validate(value)
        except Exception as error:
            raise CatalogAdapterError(f"catalog CSV produced invalid canonical data: {error}") from error
        return document, provenance_for(payload, source_uri=source_uri, source_kind="documented_csv", synthetic=False)


def load_catalog(path: Path, *, format: str | None = None) -> tuple[CatalogDocument, SourceProvenance]:
    payload = path.read_text(encoding="utf-8")
    selected = (format or path.suffix.lstrip(".")).lower()
    if selected == "json":
        return JsonCatalogAdapter().read(payload, source_uri=path.as_uri())
    if selected == "csv":
        return CsvCatalogAdapter().read(payload, source_uri=path.as_uri())
    raise CatalogAdapterError(f"unsupported catalog format: {selected!r}")


def write_canonical_json(document: CatalogDocument, destination: Path) -> None:
    destination.write_text(json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
