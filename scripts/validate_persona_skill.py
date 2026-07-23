#!/usr/bin/env python3
"""Static validator for a persona skill produced by the Hermes God Skill.

Uses only the Python standard library so it can run in a clean Hermes install.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

REQUIRED_MARKERS = (
    "capabilities",
    "safety",
    "identity",
    "mental-models",
    "heuristics",
    "expression",
    "values",
    "genealogy",
    "blind-spots",
    "soul-layer",
    "protocol",
    "update",
    "sources",
)

GENERAL_FILES = (
    "G1-conversations.md",
    "G2-expression-dna.md",
    "G3-external-views.md",
    "G4-timeline.md",
)

ALLOWED_SUBJECT_TYPES = {"public-living", "public-historical", "private", "fictional"}
ALLOWED_CONSENT_BASES = {
    "public-sources",
    "subject-consent",
    "guardian-consent",
    "self",
    "not-applicable",
}
ALLOWED_PURPOSES = {
    "public-figure-analysis",
    "scholarship",
    "creative-analysis",
    "self-reflection",
    "fictional-analysis",
}
ALLOWED_SOURCE_TYPES = {
    "primary-self",
    "primary-action",
    "primary-work",
    "contemporary-third-party",
    "later-biography",
    "aggregator/lead",
    "inference",
}
ALLOWED_RIGHTS = {
    "public-domain",
    "licensed",
    "short-quotes-only",
    "metadata-only",
    "user-provided-private",
    "no-redistribution",
}

VALIDATION_FILES = (
    "calibration.md",
    "boundary.md",
    "voice-blind-test.md",
    "final-scorecard.md",
)

PLACEHOLDER_PATTERNS = (
    r"\bTODO\b",
    r"\bTBD\b",
    r"待补",
    r"추후\s*(작성|보완)",
    r"<canonical subject>",
    r"<인물명>",
    r"<모델명>",
    r"<이름>",
    r"<가치>",
    r"<맹점>",
    r"YYYY-MM-DD",
    r"\[S\.\.\.\]",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", ""
    end = text.find("\n---\n", 4)
    if end < 0:
        return "", ""
    return text[4:end], text[end + 5 :]


def frontmatter_syntax_errors(frontmatter: str) -> list[str]:
    """Validate the conservative YAML subset used by generated skills.

    PyYAML is intentionally not required. This catches malformed mapping lines,
    tabs, odd indentation, and unterminated quoted/inline collection scalars.
    """

    errors: list[str] = []
    block_indent: int | None = None
    for lineno, line in enumerate(frontmatter.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            errors.append(f"frontmatter line {lineno} contains a tab")
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            errors.append(f"frontmatter line {lineno} uses odd indentation")
        if block_indent is not None and indent > block_indent:
            continue
        block_indent = None
        match = re.fullmatch(r"\s*([A-Za-z0-9_-]+):(?:\s*(.*))?", line)
        if not match:
            errors.append(f"frontmatter line {lineno} is not a YAML mapping entry")
            continue
        value = (match.group(2) or "").strip()
        if value in {"|", ">", "|-", ">-"}:
            block_indent = indent
            continue
        if value.startswith(('"', "'")):
            quote = value[0]
            if len(value) < 2 or not value.endswith(quote):
                errors.append(f"frontmatter line {lineno} has an unterminated quoted scalar")
        if value.startswith("[") and not value.endswith("]"):
            errors.append(f"frontmatter line {lineno} has an unterminated inline list")
        if value.startswith("{") and not value.endswith("}"):
            errors.append(f"frontmatter line {lineno} has an unterminated inline mapping")
    return errors


def frontmatter_value(frontmatter: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.*)$", frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"|", ">", "|-", ">-"}:
        lines: list[str] = []
        rest = frontmatter[match.end() :].splitlines()
        for line in rest:
            if not line.strip():
                lines.append("")
                continue
            if not line.startswith((" ", "\t")):
                break
            lines.append(line.strip())
        value = " ".join(lines).strip()
    return value.strip("'\"")


def source_ids(text: str) -> set[str]:
    return set(re.findall(r"\bS\d{3,}\b", text))


def ledger_rows(text: str) -> tuple[dict[str, list[str]], list[str]]:
    rows: dict[str, list[str]] = {}
    duplicates: list[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not re.fullmatch(r"S\d{3,}", cells[0]):
            continue
        if cells[0] in rows:
            duplicates.append(cells[0])
        rows[cells[0]] = cells
    return rows, duplicates


def marker_section(text: str, marker: str, next_marker: str) -> str:
    start_token = f"<!-- god-skill:{marker} -->"
    end_token = f"<!-- god-skill:{next_marker} -->"
    start = text.find(start_token)
    if start < 0:
        return ""
    end = text.find(end_token, start + len(start_token))
    return text[start : end if end >= 0 else len(text)]


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return None


def blockquote_lengths(text: str) -> list[int]:
    lengths: list[int] = []
    current = 0
    for line in text.splitlines():
        if line.startswith(">"):
            current += len(line.lstrip("> "))
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_missing_file(
    path: Path,
    label: str,
    errors: list[str],
    warnings: list[str],
    draft: bool,
) -> None:
    message = f"missing {label}: {path}"
    (warnings if draft else errors).append(message)


def validate(project: Path, draft: bool, allow_no_specialist: bool) -> dict:
    if project.is_file():
        if project.name != "SKILL.md":
            return {
                "valid": False,
                "errors": [f"file input must be named SKILL.md, got: {project.name}"],
                "warnings": [],
                "metrics": {},
            }
        skill_path = project
        project = project.parent
    else:
        skill_path = project / "SKILL.md"

    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, object] = {}

    if not skill_path.exists():
        errors.append(f"missing final SKILL.md: {skill_path}")
        return {"valid": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    for candidate in project.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in {".md", ".json"}:
            try:
                candidate.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"invalid UTF-8 input: {candidate}")

    skill = read_text(skill_path)
    frontmatter, body = parse_frontmatter(skill)
    metrics["skill_chars"] = len(skill)
    metrics["skill_lines"] = len(skill.splitlines())

    subject_type = ""
    soul_layer_enabled = ""
    source_cutoff = ""
    declared_primary = ""
    declared_independent = ""
    declared_recent = ""
    is_minor: bool | None = None
    consent_basis = ""
    research_purpose = ""
    private_or_minor = False
    soul_disabled = False

    if not frontmatter:
        errors.append("SKILL.md frontmatter is missing or malformed")
    else:
        errors.extend(frontmatter_syntax_errors(frontmatter))
        name = frontmatter_value(frontmatter, "name")
        description = frontmatter_value(frontmatter, "description")
        subject_type = frontmatter_value(frontmatter, "subject_type")
        soul_layer_enabled = frontmatter_value(frontmatter, "soul_layer_enabled")
        source_cutoff = frontmatter_value(frontmatter, "source_cutoff")
        declared_primary = frontmatter_value(frontmatter, "primary_source_count")
        declared_independent = frontmatter_value(frontmatter, "independent_source_count")
        declared_recent = frontmatter_value(frontmatter, "recent_source_count")
        is_minor = parse_bool(frontmatter_value(frontmatter, "is_minor"))
        consent_basis = frontmatter_value(frontmatter, "consent_basis")
        research_purpose = frontmatter_value(frontmatter, "research_purpose")
        private_or_minor = bool(
            re.search(r"private|minor|비공개|사인|미성년", subject_type, flags=re.IGNORECASE)
        )
        soul_disabled = soul_layer_enabled.lower() in {"false", "no", "0", "disabled"}
        metrics["name"] = name
        metrics["description_chars"] = len(description)
        metrics["subject_type"] = subject_type
        metrics["is_minor"] = is_minor
        metrics["consent_basis"] = consent_basis
        metrics["research_purpose"] = research_purpose
        metrics["soul_layer_enabled"] = soul_layer_enabled
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
            errors.append("frontmatter name must be lowercase-hyphenated and <=64 chars")
        if not description:
            errors.append("frontmatter description is missing")
        elif len(description) > 1024:
            errors.append(f"frontmatter description exceeds 1024 chars: {len(description)}")
        required_provenance = (
            "god_skill:",
            "subject_type:",
            "is_minor:",
            "consent_basis:",
            "research_purpose:",
            "source_cutoff:",
            "primary_source_count:",
            "independent_source_count:",
            "recent_source_count:",
            "confidence:",
            "soul_layer_enabled:",
            "private_sensitive_inference:",
            "high_stakes_use:",
            "impersonation:",
        )
        for field in required_provenance:
            if field not in frontmatter:
                (warnings if draft else errors).append(
                    f"frontmatter provenance is missing {field.rstrip(':')}"
                )
        if subject_type not in ALLOWED_SUBJECT_TYPES:
            errors.append(f"unsupported subject_type: {subject_type or '<missing>'}")
        if is_minor is None:
            errors.append("is_minor must be true or false")
        elif is_minor and subject_type != "fictional":
            errors.append("deep person-distillation of a real minor is prohibited")
        if consent_basis not in ALLOWED_CONSENT_BASES:
            errors.append(f"unsupported consent_basis: {consent_basis or '<missing>'}")
        if research_purpose not in ALLOWED_PURPOSES:
            errors.append(f"unsupported research_purpose: {research_purpose or '<missing>'}")
        if subject_type == "private" and consent_basis not in {"subject-consent", "self"}:
            errors.append("private subjects require subject-consent or self consent_basis")
        if subject_type == "fictional" and consent_basis != "not-applicable":
            errors.append("fictional subjects require consent_basis: not-applicable")
        if parse_iso_date(source_cutoff) is None:
            errors.append("source_cutoff must be a valid ISO date")
        if frontmatter_value(frontmatter, "private_sensitive_inference").lower() not in {
            "false",
            "no",
            "0",
            "prohibited",
        }:
            errors.append("private_sensitive_inference must be false/prohibited")
        if frontmatter_value(frontmatter, "high_stakes_use").lower() != "prohibited":
            errors.append("high_stakes_use must be prohibited")
        if frontmatter_value(frontmatter, "impersonation").lower() != "prohibited":
            errors.append("impersonation must be prohibited")
        if (private_or_minor or is_minor is True) and not soul_disabled:
            errors.append("private/minor subjects require soul_layer_enabled: false")

    if not body.strip():
        errors.append("SKILL.md body is empty")
    if len(skill) > 100_000:
        errors.append(f"SKILL.md exceeds Hermes 100000-char limit: {len(skill)}")
    quote_lengths = blockquote_lengths(skill)
    metrics["max_blockquote_chars"] = max(quote_lengths, default=0)
    if any(length > 1_200 for length in quote_lengths):
        errors.append("final SKILL.md contains a blockquote over 1200 chars; package metadata or a short quote instead")
    if sum(quote_lengths) > 5_000:
        errors.append("final SKILL.md contains over 5000 quoted characters in total")
    if re.search(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)", skill):
        errors.append("final SKILL.md leaks an absolute local user path")

    missing_markers = [
        marker
        for marker in REQUIRED_MARKERS
        if f"<!-- god-skill:{marker} -->" not in skill
    ]
    metrics["required_markers_present"] = len(REQUIRED_MARKERS) - len(missing_markers)
    if missing_markers:
        errors.append("missing machine-readable sections: " + ", ".join(missing_markers))

    safety_section = marker_section(skill, "safety", "identity")
    if safety_section and len(safety_section.strip()) < 120:
        errors.append("safety section is too thin (<120 chars)")
    if private_or_minor:
        soul_section = marker_section(skill, "soul-layer", "protocol")
        if not re.search(r"disabled|비활성|생략|금지", soul_section, flags=re.IGNORECASE):
            errors.append("private/minor soul-layer section must explicitly state that it is disabled")

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, skill, flags=re.IGNORECASE):
            errors.append(f"unresolved placeholder matched: {pattern}")

    run_state_path = project / "run-state.json"
    run_state: dict[str, object] = {}
    if not run_state_path.exists():
        errors.append(f"missing run-state.json: {run_state_path}")
    else:
        try:
            loaded_state = json.loads(read_text(run_state_path))
            if not isinstance(loaded_state, dict):
                raise ValueError("root must be an object")
            run_state = loaded_state
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"malformed run-state.json: {exc}")
    if run_state:
        state_subject = run_state.get("subject", {})
        state_scope = run_state.get("scope", {})
        if not isinstance(state_subject, dict) or not isinstance(state_scope, dict):
            errors.append("run-state subject and scope must be objects")
        else:
            expected_pairs = (
                ("subject.type", state_subject.get("type"), subject_type),
                ("subject.is_minor", state_subject.get("is_minor"), is_minor),
                ("subject.consent_basis", state_subject.get("consent_basis"), consent_basis),
                ("scope.purpose", state_scope.get("purpose"), research_purpose),
                ("scope.soul_layer", state_scope.get("soul_layer"), not soul_disabled),
                ("scope.high_stakes_use", state_scope.get("high_stakes_use"), "prohibited"),
                ("scope.source_cutoff", state_scope.get("source_cutoff"), source_cutoff),
            )
            for label, observed, expected in expected_pairs:
                if observed != expected:
                    errors.append(
                        f"run-state/frontmatter mismatch for {label}: {observed!r} != {expected!r}"
                    )
        if not draft:
            phases = run_state.get("phases", {})
            if not isinstance(phases, dict):
                errors.append("run-state phases must be an object")
            else:
                required_phases = {
                    "identity": {"verified"},
                    "ingest": {"verified"},
                    "wave_1": {"verified"},
                    "wave_2": {"verified"},
                    "wave_3_g5": {"omitted"} if soul_disabled else {"verified"},
                    "synthesis": {"verified"},
                    "static_validation": {"in_progress", "verified"},
                    "independent_validation": {"verified"},
                }
                for phase, allowed in required_phases.items():
                    if phases.get(phase) not in allowed:
                        errors.append(
                            f"run-state phase {phase} must be one of {sorted(allowed)}, got {phases.get(phase)!r}"
                        )

            artifacts = run_state.get("artifacts", {})
            if not isinstance(artifacts, dict):
                errors.append("run-state artifacts must be an object")
                artifacts = {}
            artifact_by_path: dict[str, dict[str, object]] = {}
            for artifact_name, artifact in artifacts.items():
                if not isinstance(artifact, dict):
                    errors.append(f"run-state artifact {artifact_name} must be an object")
                    continue
                rel_path = artifact.get("path")
                if not isinstance(rel_path, str) or not rel_path:
                    errors.append(f"run-state artifact {artifact_name} lacks a relative path")
                    continue
                parsed_path = Path(rel_path)
                if parsed_path.is_absolute() or ".." in parsed_path.parts:
                    errors.append(f"run-state artifact {artifact_name} has unsafe path: {rel_path}")
                    continue
                normalized = parsed_path.as_posix()
                if normalized in artifact_by_path:
                    errors.append(f"run-state has duplicate artifact path: {normalized}")
                artifact_by_path[normalized] = artifact

            required_artifacts = [
                "SKILL.md",
                "references/source-ledger.md",
                "references/source-index.md",
                *(f"references/research/general/{name}" for name in GENERAL_FILES),
                "references/research/general/G5-omission.md"
                if soul_disabled
                else "references/research/general/G5-soul-layer.md",
                *(f"validation/{name}" for name in VALIDATION_FILES),
                *(
                    path.relative_to(project).as_posix()
                    for path in sorted((project / "references/research/specialist").glob("A*.md"))
                ),
            ]
            for rel_path in required_artifacts:
                artifact = artifact_by_path.get(rel_path)
                if artifact is None:
                    errors.append(f"run-state lacks verified artifact entry: {rel_path}")
                    continue
                artifact_path = project / rel_path
                if artifact.get("status") != "verified":
                    errors.append(f"run-state artifact is not verified: {rel_path}")
                if artifact_path.is_file():
                    expected_hash = f"sha256:{file_sha256(artifact_path)}"
                    if artifact.get("sha256") != expected_hash:
                        errors.append(f"run-state artifact hash mismatch: {rel_path}")

    ledger_path = project / "references" / "source-ledger.md"
    if not ledger_path.exists():
        errors.append(f"missing source ledger: {ledger_path}")
        ledger = ""
    else:
        ledger = read_text(ledger_path)

    rows, duplicate_ids = ledger_rows(ledger)
    ledger_ids = set(rows)
    unstructured_ids = sorted(source_ids(ledger) - ledger_ids)
    skill_ids = source_ids(skill)
    unresolved_ids = sorted(skill_ids - ledger_ids)
    metrics["ledger_source_count"] = len(ledger_ids)
    metrics["skill_citation_count"] = len(skill_ids)
    if not ledger_ids:
        errors.append("source ledger contains no structured source rows such as | S001 | ... |")
    elif len(ledger_ids) < 15:
        warnings.append(f"low-evidence run: only {len(ledger_ids)} source IDs (<15)")
    if duplicate_ids:
        errors.append("duplicate source-ledger IDs: " + ", ".join(sorted(set(duplicate_ids))))
    if unstructured_ids:
        errors.append(
            "source IDs appear outside a structured ledger row: " + ", ".join(unstructured_ids)
        )
    primary_count = 0
    independent_keys: set[str] = set()
    recent_count = 0
    cutoff_date = parse_iso_date(source_cutoff)
    for source_id, cells in rows.items():
        if len(cells) < 12:
            errors.append(f"source-ledger row {source_id} has fewer than 12 columns")
            continue
        source_type = cells[1]
        published = cells[4]
        location = cells[5]
        accessed = cells[6]
        rights = cells[8]
        independence_key = cells[9]
        retrieved = cells[10].lower()
        snapshot = cells[11]
        if source_type not in ALLOWED_SOURCE_TYPES:
            errors.append(f"source-ledger row {source_id} has unsupported type: {source_type}")
        if not location:
            errors.append(f"source-ledger row {source_id} lacks a URL/path locator")
        if parse_iso_date(accessed) is None:
            errors.append(f"source-ledger row {source_id} has invalid accessed date: {accessed}")
        if rights not in ALLOWED_RIGHTS:
            errors.append(f"source-ledger row {source_id} has unsupported rights status: {rights}")
        if not independence_key:
            errors.append(f"source-ledger row {source_id} lacks an independence key")
        if retrieved not in {"yes", "partial", "no"}:
            errors.append(f"source-ledger row {source_id} has invalid retrieved status: {retrieved}")
        if retrieved in {"yes", "partial"} and not re.fullmatch(
            r"(?:sha256:[0-9a-fA-F]{64}|not-retained|n/a)", snapshot
        ):
            errors.append(f"source-ledger row {source_id} has invalid snapshot value: {snapshot}")
        if source_type.startswith("primary-"):
            primary_count += 1
        if source_type not in {"aggregator/lead", "inference"} and retrieved in {"yes", "partial"}:
            independent_keys.add(independence_key)
        published_date = parse_iso_date(published)
        if (
            cutoff_date
            and published_date
            and cutoff_date - timedelta(days=366) <= published_date <= cutoff_date
            and source_type not in {"aggregator/lead", "inference"}
            and retrieved in {"yes", "partial"}
        ):
            recent_count += 1

    computed_counts = {
        "primary_source_count": primary_count,
        "independent_source_count": len(independent_keys),
        "recent_source_count": recent_count,
    }
    metrics.update(computed_counts)
    for label, declared in (
        ("primary_source_count", declared_primary),
        ("independent_source_count", declared_independent),
        ("recent_source_count", declared_recent),
    ):
        if not declared.isdigit():
            errors.append(f"frontmatter {label} must be a non-negative integer")
        elif int(declared) != computed_counts[label]:
            errors.append(
                f"frontmatter {label}={declared} does not match recomputed value {computed_counts[label]}"
            )
    if subject_type == "public-living" and recent_count < 1:
        errors.append("public-living subjects require at least one independent source from the final 12 months")

    source_index_path = project / "references" / "source-index.md"
    if not source_index_path.exists():
        errors.append(f"missing sanitized source index: {source_index_path}")
    else:
        source_index = read_text(source_index_path)
        if re.search(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)", source_index):
            errors.append("source-index.md leaks an absolute local user path")
        index_ids = source_ids(source_index)
        if index_ids != ledger_ids:
            missing = sorted(ledger_ids - index_ids)
            extra = sorted(index_ids - ledger_ids)
            errors.append(
                f"source-index IDs do not match ledger; missing={missing}, extra={extra}"
            )
    if not skill_ids:
        errors.append("final SKILL.md contains no source citations")
    if unresolved_ids:
        errors.append("SKILL.md cites IDs absent from ledger: " + ", ".join(unresolved_ids))

    mental_models = marker_section(skill, "mental-models", "heuristics")
    if len(source_ids(mental_models)) < 2:
        errors.append("mental-models section requires at least two source IDs")
    if not re.search(r"\[TENSION\]|counterexample|반례|反例", mental_models, re.IGNORECASE):
        errors.append("mental-models section lacks a counterexample/tension")
    heuristics = marker_section(skill, "heuristics", "expression")
    if not source_ids(heuristics):
        errors.append("heuristics section requires source citations")
    if not re.search(r"failure|실패|적용 경계|boundary", heuristics, re.IGNORECASE):
        errors.append("heuristics section lacks a failure condition/boundary")
    blind_spots = marker_section(skill, "blind-spots", "soul-layer")
    if not source_ids(blind_spots):
        errors.append("blind-spots section requires source citations")
    if not re.search(r"counterexample|반례|反例", blind_spots, re.IGNORECASE):
        errors.append("blind-spots section lacks a counterexample")
    if not soul_disabled:
        soul_section = marker_section(skill, "soul-layer", "protocol")
        if len(source_ids(soul_section)) < 2:
            errors.append("enabled soul-layer section requires at least two source IDs")
        if "[INFERENCE]" not in soul_section:
            errors.append("enabled soul-layer section must label its claims [INFERENCE]")

    general_dir = project / "references" / "research" / "general"
    general_metrics: dict[str, int] = {}
    for filename in GENERAL_FILES:
        path = general_dir / filename
        if not path.exists():
            add_missing_file(path, "general research file", errors, warnings, draft)
            continue
        text = read_text(path)
        general_metrics[filename] = len(text)
        if len(text.strip()) < 200:
            (warnings if draft else errors).append(f"research file is too thin (<200 chars): {path}")
        if not source_ids(text):
            (warnings if draft else errors).append(f"research file contains no source citations: {path}")

    g5_soul_path = general_dir / "G5-soul-layer.md"
    g5_omission_path = general_dir / "G5-omission.md"
    if soul_disabled:
        if g5_soul_path.exists():
            errors.append("soul_layer_enabled: false forbids G5-soul-layer.md; use G5-omission.md")
        if not g5_omission_path.exists():
            add_missing_file(g5_omission_path, "G5 privacy omission record", errors, warnings, draft)
        else:
            omission = read_text(g5_omission_path)
            general_metrics[g5_omission_path.name] = len(omission)
            if len(omission.strip()) < 200:
                (warnings if draft else errors).append(f"G5 omission record is too thin: {g5_omission_path}")
            if not re.search(r"disabled|비활성|omitted|생략|privacy|동의|consent", omission, re.IGNORECASE):
                errors.append("G5 omission record lacks a privacy/consent rationale")
    else:
        if not g5_soul_path.exists():
            add_missing_file(g5_soul_path, "G5 soul-layer research file", errors, warnings, draft)
        else:
            g5_text = read_text(g5_soul_path)
            general_metrics[g5_soul_path.name] = len(g5_text)
            if len(g5_text.strip()) < 200:
                (warnings if draft else errors).append(f"G5 research file is too thin: {g5_soul_path}")
            if len(source_ids(g5_text)) < 2:
                errors.append("G5-soul-layer.md requires at least two source IDs")
            if not re.search(r"confidence|置信度|신뢰도|확신도", g5_text, flags=re.IGNORECASE):
                errors.append("G5-soul-layer.md lacks confidence labels")
            if not re.search(r"counterexample|反例|반례|falsif", g5_text, flags=re.IGNORECASE):
                errors.append("G5-soul-layer.md lacks counterexamples/falsifiability")
    metrics["general_file_chars"] = general_metrics

    specialist_dir = project / "references" / "research" / "specialist"
    specialist_files = sorted(specialist_dir.glob("A*.md")) if specialist_dir.exists() else []
    metrics["specialist_file_count"] = len(specialist_files)
    if not specialist_files and not allow_no_specialist:
        (warnings if draft else errors).append("no specialist A-lane report found")
    for path in specialist_files:
        specialist_text = read_text(path)
        if len(specialist_text.strip()) < 200:
            (warnings if draft else errors).append(f"specialist report is too thin: {path}")
        if not source_ids(specialist_text):
            (warnings if draft else errors).append(f"specialist report contains no source citations: {path}")

    validation_dir = project / "validation"
    validation_present = 0
    validation_hard_fail_counts: dict[str, int | None] = {}
    skill_sha256 = hashlib.sha256(skill.encode("utf-8")).hexdigest()
    metrics["skill_sha256"] = skill_sha256
    for filename in VALIDATION_FILES:
        path = validation_dir / filename
        if not path.exists():
            add_missing_file(path, "independent validation artifact", errors, warnings, draft)
        else:
            validation_present += 1
            text = read_text(path)
            if len(text.strip()) < 150:
                (warnings if draft else errors).append(
                    f"independent validation artifact is too thin (<150 chars): {path}"
                )

            def report_field(key: str) -> str:
                match = re.search(rf"(?mi)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
                return match.group(1).strip() if match else ""

            reviewer_id = report_field("reviewer_task_or_session")
            if not reviewer_id or reviewer_id.startswith("<"):
                errors.append(f"independent validation lacks reviewer task/session ID: {path}")
            if report_field("reviewer_independent").lower() != "true":
                errors.append(f"independent validation must declare reviewer_independent: true: {path}")
            expected_revision = f"sha256:{skill_sha256}"
            if report_field("reviewed_revision") != expected_revision:
                errors.append(f"independent validation reviewed_revision does not match final SKILL.md: {path}")

            count_matches = [
                int(value)
                for value in re.findall(
                    r"(?mi)^\s*hard_fail_count\s*:\s*(\d+)\s*$",
                    text,
                )
            ]
            if count_matches:
                hard_fail_count = max(count_matches)
                validation_hard_fail_counts[filename] = hard_fail_count
                if hard_fail_count > 0:
                    errors.append(f"independent validation reports hard failures in {path}: {hard_fail_count}")
                if hard_fail_count == 0 and report_field("verdict").upper() != "PASS":
                    errors.append(f"zero-hard-fail validation must declare verdict: PASS: {path}")
            else:
                validation_hard_fail_counts[filename] = None
                (warnings if draft else errors).append(
                    f"independent validation lacks explicit hard_fail_count: {path}"
                )
    metrics["validation_artifacts_present"] = validation_present
    metrics["validation_hard_fail_counts"] = validation_hard_fail_counts

    all_research = "\n".join(
        read_text(path)
        for path in list(general_dir.glob("*.md")) + specialist_files
        if path.exists()
    )
    research_ids = source_ids(all_research)
    metrics["research_citation_count"] = len(research_ids)
    missing_research_ids = sorted(research_ids - ledger_ids)
    if missing_research_ids:
        errors.append("research files cite IDs absent from ledger: " + ", ".join(missing_research_ids))

    return {
        "valid": not errors,
        "mode": "draft" if draft else "strict",
        "project": str(project.resolve()),
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a persona skill project produced by Hermes God Skill."
    )
    parser.add_argument("project", type=Path, help="Project directory or final SKILL.md")
    parser.add_argument("--draft", action="store_true", help="Downgrade missing research/QA files to warnings")
    parser.add_argument(
        "--allow-no-specialist",
        action="store_true",
        help="Allow a run with no A-lane report when the scope explicitly does not need one",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate(args.project.expanduser(), args.draft, args.allow_no_specialist)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("PASS" if result["valid"] else "FAIL", result.get("project", ""))
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARN: {item}")
        print("METRICS:", json.dumps(result["metrics"], ensure_ascii=False, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
