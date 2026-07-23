from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_persona_skill.py"
SPEC = importlib.util.spec_from_file_location("validate_persona_skill", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

MARKERS = (
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


class PersonaSkillValidatorTests(unittest.TestCase):
    def write_validation_reports(self, project: Path) -> None:
        skill_hash = hashlib.sha256((project / "SKILL.md").read_bytes()).hexdigest()
        validation = project / "validation"
        validation.mkdir(exist_ok=True)
        for filename in MODULE.VALIDATION_FILES:
            (validation / filename).write_text(
                f"# {filename}\n\n"
                f"review_type: {filename.removesuffix('.md')}\n"
                f"reviewed_artifact: {project / 'SKILL.md'}\n"
                f"reviewed_revision: sha256:{skill_hash}\n"
                f"reviewer_task_or_session: child-{filename.removesuffix('.md')}-001\n"
                "reviewer_independent: true\n"
                "hard_fail_count: 0\n"
                "verdict: PASS\n\n"
                "The independent reviewer sampled evidence, reproduced the specified test, "
                "recorded counterexamples, and found no blocking issue in the exact reviewed artifact.\n",
                encoding="utf-8",
            )

    def refresh_run_state(self, project: Path) -> None:
        state_path = project / "run-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        soul_enabled = state["scope"]["soul_layer"]
        state["phases"] = {
            "identity": "verified",
            "ingest": "verified",
            "wave_1": "verified",
            "wave_2": "verified",
            "wave_3_g5": "verified" if soul_enabled else "omitted",
            "synthesis": "verified",
            "static_validation": "in_progress",
            "independent_validation": "verified",
            "install": "pending",
        }
        paths = [
            project / "SKILL.md",
            project / "references/source-ledger.md",
            project / "references/source-index.md",
            *sorted((project / "references/research/general").glob("*.md")),
            *sorted((project / "references/research/specialist").glob("A*.md")),
            *(project / "validation" / name for name in MODULE.VALIDATION_FILES),
        ]
        state["artifacts"] = {
            f"artifact_{index:02d}": {
                "path": path.relative_to(project).as_posix(),
                "sha256": f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
                "status": "verified",
            }
            for index, path in enumerate(paths, start=1)
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def make_valid_project(self, root: Path) -> Path:
        project = root / "ada-lovelace-perspective"
        project.mkdir(parents=True)
        sections = {
            "capabilities": "Applies a source-grounded reasoning model and explicitly states uncertainty [S001].",
            "safety": (
                "This is a source-grounded model, not the person's current speech or identity. "
                "No diagnosis, private sensitive inference, impersonation, credential claim, "
                "or hiring, insurance, investigation, medical, legal, or financial high-stakes use is allowed."
            ),
            "identity": "The subject and evidence boundary are identified from historical records [S001].",
            "mental-models": (
                "[FACT] A model is supported across distinct contexts [S001] [S002]. "
                "[TENSION] Counterexample evidence limits the model and prevents universal application."
            ),
            "heuristics": (
                "[FACT] If analytical notation reduces ambiguity, then formalize the problem [S003]. "
                "Failure boundary: do not apply where the available evidence is incomplete."
            ),
            "expression": "Expression patterns are medium-dependent and source-bound [S004].",
            "values": "Values are inferred conservatively from repeated choices [S005].",
            "genealogy": "Intellectual influences and disagreements remain separately sourced [S006].",
            "blind-spots": (
                "[INFERENCE] A possible blind spot appears in one context [S004]. "
                "Counterexample: another context shows adaptation rather than rigidity."
            ),
            "soul-layer": (
                "[INFERENCE] A cautious meaning-investment hypothesis is supported by [S005] [S006]. "
                "Confidence: medium. Counterexample: practical constraints may explain the same behavior."
            ),
            "protocol": "Answer with evidence labels and decline identity impersonation [S001].",
            "update": "Recompute source counts and revalidate when evidence changes [S002].",
            "sources": "The sanitized runtime bibliography is references/source-index.md [S001].",
        }
        marker_text = "\n\n".join(
            f"<!-- god-skill:{name} -->\n## {name}\n\n{sections[name]}" for name in MARKERS
        )
        (project / "SKILL.md").write_text(
            "---\n"
            "name: ada-lovelace-perspective\n"
            "description: Evidence-grounded Ada Lovelace perspective.\n"
            "version: 0.1.0\n"
            "metadata:\n"
            "  god_skill:\n"
            "    subject_type: public-historical\n"
            "    is_minor: false\n"
            "    consent_basis: public-sources\n"
            "    research_purpose: scholarship\n"
            "    source_cutoff: 2026-01-01\n"
            "    primary_source_count: 15\n"
            "    independent_source_count: 15\n"
            "    recent_source_count: 0\n"
            "    confidence: medium\n"
            "    soul_layer_enabled: true\n"
            "    private_sensitive_inference: false\n"
            "    high_stakes_use: prohibited\n"
            "    impersonation: prohibited\n"
            "    source_index: references/source-index.md\n"
            "---\n"
            "# Ada Lovelace\n\n"
            + marker_text
            + "\n",
            encoding="utf-8",
        )

        (project / "run-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "subject": {
                        "display_name": "Ada Lovelace",
                        "canonical_id": "ada-lovelace",
                        "type": "public-historical",
                        "is_minor": False,
                        "consent_basis": "public-sources",
                    },
                    "scope": {
                        "language": "en",
                        "purpose": "scholarship",
                        "soul_layer": True,
                        "high_stakes_use": "prohibited",
                        "source_cutoff": "2026-01-01",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        refs = project / "references"
        refs.mkdir()
        ledger_rows = "\n".join(
            f"| S{i:03d} | primary-work | Author | Source {i} | 1843-01-01 | "
            f"https://example.com/source-{i} | 2026-01-01 | high | public-domain | "
            f"source-{i} | yes | n/a |"
            for i in range(1, 16)
        )
        (refs / "source-ledger.md").write_text(
            "# Source Ledger\n\n"
            "| ID | Type | Author | Title | Published | Location | Accessed | Reliability | Rights | Independence | Retrieved | Snapshot |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            + ledger_rows
            + "\n",
            encoding="utf-8",
        )
        index_rows = "\n".join(
            f"| S{i:03d} | Author | Source {i} | https://example.com/source-{i} | public-domain |"
            for i in range(1, 16)
        )
        (refs / "source-index.md").write_text(
            "# Sanitized Source Index\n\n| ID | Author | Title | Public locator | Rights |\n"
            "|---|---|---|---|---|\n"
            + index_rows
            + "\n",
            encoding="utf-8",
        )

        general = refs / "research" / "general"
        general.mkdir(parents=True)
        for filename in MODULE.GENERAL_FILES:
            (general / filename).write_text(
                f"# {filename}\n\nEvidence [S001].\n" + ("Substantive research sentence. " * 15),
                encoding="utf-8",
            )
        (general / "G5-soul-layer.md").write_text(
            "# G5 soul layer\n\nEvidence [S001] and [S002]. Confidence: medium. "
            "Counterexample: practical constraints could falsify the hypothesis.\n"
            + ("Conservative source-grounded synthesis. " * 12),
            encoding="utf-8",
        )

        specialist = refs / "research" / "specialist"
        specialist.mkdir()
        (specialist / "A1-writings.md").write_text(
            "# Writings\n\nEvidence [S002].\n" + ("Substantive specialist analysis. " * 15),
            encoding="utf-8",
        )

        self.write_validation_reports(project)
        self.refresh_run_state(project)
        return project

    def test_valid_project_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertTrue(result["valid"], result)
            self.assertEqual(result["metrics"]["ledger_source_count"], 15)
            self.assertEqual(result["metrics"]["independent_source_count"], 15)
            self.assertEqual(result["metrics"]["validation_artifacts_present"], 4)

    def test_template_like_project_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "bad-perspective"
            project.mkdir()
            (project / "SKILL.md").write_text(
                "---\nname: BAD NAME\ndescription: TODO\n---\n# <인물명>\n",
                encoding="utf-8",
            )
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            joined = "\n".join(result["errors"])
            self.assertIn("frontmatter name", joined)
            self.assertIn("unresolved placeholder", joined)
            self.assertIn("source ledger", joined)

    def test_unresolved_source_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nUnsupported [S999].\n", encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("S999" in error for error in result["errors"]))

    def test_reported_hard_failure_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill_hash = hashlib.sha256((project / "SKILL.md").read_bytes()).hexdigest()
            report = project / "validation" / "calibration.md"
            report.write_text(
                "# Calibration\n\nreviewer_task_or_session: child-calibration-001\n"
                "reviewer_independent: true\n"
                f"reviewed_revision: sha256:{skill_hash}\n"
                "hard_fail_count: 2\nverdict: FAIL\n\n"
                "Two source-opposite calibration results were reproduced independently and recorded.\n",
                encoding="utf-8",
            )
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("hard failures" in error for error in result["errors"]))

    def test_empty_validation_artifact_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            (project / "validation" / "boundary.md").write_text("", encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertIn("too thin", "\n".join(result["errors"]))

    def test_spoofed_qa_revision_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            report = project / "validation" / "boundary.md"
            report.write_text(report.read_text().replace("sha256:", "sha256:deadbeef"), encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("reviewed_revision" in error for error in result["errors"]))

    def test_malformed_quoted_frontmatter_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(
                skill.read_text().replace(
                    "description: Evidence-grounded Ada Lovelace perspective.",
                    'description: "unterminated',
                ),
                encoding="utf-8",
            )
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("unterminated quoted scalar" in error for error in result["errors"]))

    def test_private_subject_requires_disabled_soul_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(skill.read_text().replace("subject_type: public-historical", "subject_type: private"), encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("private/minor" in error for error in result["errors"]))

    def test_private_safe_omission_path_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            text = skill.read_text()
            text = text.replace("subject_type: public-historical", "subject_type: private")
            text = text.replace("consent_basis: public-sources", "consent_basis: subject-consent")
            text = text.replace("research_purpose: scholarship", "research_purpose: self-reflection")
            text = text.replace("soul_layer_enabled: true", "soul_layer_enabled: false")
            start = text.index("<!-- god-skill:soul-layer -->")
            end = text.index("<!-- god-skill:protocol -->")
            text = text[:start] + (
                "<!-- god-skill:soul-layer -->\n## soul-layer\n\n"
                "Disabled and omitted because privacy and explicit consent boundaries prohibit hidden-trait inference.\n\n"
            ) + text[end:]
            skill.write_text(text, encoding="utf-8")
            state_path = project / "run-state.json"
            state = json.loads(state_path.read_text())
            state["subject"].update({"type": "private", "consent_basis": "subject-consent"})
            state["scope"].update({"purpose": "self-reflection", "soul_layer": False})
            state_path.write_text(json.dumps(state), encoding="utf-8")
            g5 = project / "references" / "research" / "general" / "G5-soul-layer.md"
            g5.unlink()
            (g5.parent / "G5-omission.md").write_text(
                "# G5 omission\n\nSoul-layer inference is disabled and omitted for privacy and consent reasons. "
                + ("No hidden sensitive trait inference is performed. " * 12),
                encoding="utf-8",
            )
            self.write_validation_reports(project)
            self.refresh_run_state(project)
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertTrue(result["valid"], result)

    def test_pending_run_state_phase_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            state_path = project / "run-state.json"
            state = json.loads(state_path.read_text())
            state["phases"]["synthesis"] = "pending"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("phase synthesis" in error for error in result["errors"]))

    def test_stale_run_state_artifact_hash_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            g1 = project / "references/research/general/G1-conversations.md"
            g1.write_text(g1.read_text() + "\nChanged after verification.\n", encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("artifact hash mismatch" in error for error in result["errors"]))

    def test_real_minor_is_prohibited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(skill.read_text().replace("is_minor: false", "is_minor: true"), encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("real minor" in error for error in result["errors"]))

    def test_inflated_source_counts_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(skill.read_text().replace("independent_source_count: 15", "independent_source_count: 999"), encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("recomputed value" in error for error in result["errors"]))

    def test_absolute_path_in_source_index_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            index = project / "references" / "source-index.md"
            index.write_text(index.read_text() + "\n/Users/alice/private/raw.txt\n", encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("absolute local user path" in error for error in result["errors"]))

    def test_long_verbatim_blockquote_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            skill = project / "SKILL.md"
            skill.write_text(skill.read_text() + "\n> " + ("copyrighted text " * 100) + "\n", encoding="utf-8")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("blockquote over 1200" in error for error in result["errors"]))

    def test_invalid_utf8_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            (project / "references" / "bad.md").write_bytes(b"\xff\xfe")
            result = MODULE.validate(project, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("invalid UTF-8" in error for error in result["errors"]))

    def test_decoy_file_input_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_valid_project(Path(tmp))
            decoy = project / "NOT-SKILL.md"
            decoy.write_text((project / "SKILL.md").read_text(), encoding="utf-8")
            result = MODULE.validate(decoy, draft=False, allow_no_specialist=False)
            self.assertFalse(result["valid"])
            self.assertTrue(any("must be named SKILL.md" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
