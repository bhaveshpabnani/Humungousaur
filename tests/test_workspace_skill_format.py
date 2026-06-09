from __future__ import annotations

import re
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.tools import default_tools
from humungousaur.tools.skill_tools import AgentSkillCatalogTool


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPECTED_SKILL_DOMAINS = {
    "agent-core",
    "browser-web",
    "commerce-travel",
    "communications",
    "creative-design",
    "delegation-agents",
    "desktop-control",
    "integrations",
    "office-productivity",
    "software-engineering",
    "voice-media",
}


class WorkspaceSkillFormatTests(unittest.TestCase):
    def test_workspace_skills_follow_agent_skill_standard(self) -> None:
        skill_files = sorted((REPO_ROOT / "skills").rglob("SKILL.md"))

        self.assertGreaterEqual(len(skill_files), 17)
        for path in skill_files:
            metadata = _frontmatter(path)
            relative = path.relative_to(REPO_ROOT).as_posix()
            with self.subTest(skill=relative):
                name = metadata.get("name", "")
                description = metadata.get("description", "")
                compatibility = metadata.get("compatibility", "")

                self.assertTrue(metadata, "SKILL.md must start with YAML frontmatter.")
                self.assertRegex(name, SKILL_NAME_RE)
                self.assertLessEqual(len(name), 64)
                self.assertEqual(name, path.parent.name)
                self.assertTrue(description.strip())
                self.assertLessEqual(len(description), 1024)
                if compatibility:
                    self.assertLessEqual(len(compatibility), 500)

    def test_workspace_skills_are_grouped_by_domain_folder(self) -> None:
        skills_root = REPO_ROOT / "skills"
        top_level_skill_files = sorted(skills_root.glob("*/SKILL.md"))
        domains = {path.name for path in skills_root.iterdir() if path.is_dir()}

        self.assertEqual(domains, EXPECTED_SKILL_DOMAINS)
        self.assertEqual({path.parent.name for path in top_level_skill_files}, EXPECTED_SKILL_DOMAINS)
        for domain in EXPECTED_SKILL_DOMAINS:
            with self.subTest(domain=domain):
                self.assertTrue((skills_root / domain / "SKILL.md").is_file())
                self.assertTrue(list((skills_root / domain).glob("*/SKILL.md")))

    def test_skill_catalog_can_list_more_than_one_hundred_workspace_skills(self) -> None:
        config = AgentConfig(workspace=REPO_ROOT, data_dir=REPO_ROOT / "artifacts").normalized()
        schema = AgentSkillCatalogTool().input_schema

        self.assertEqual(schema["properties"]["limit"]["maximum"], 300)

        result = AgentSkillCatalogTool().execute({"source": "workspace", "limit": 300}, config)

        self.assertEqual(result.output["source"], "workspace")
        self.assertGreaterEqual(len(result.output["workspace_skills"]), 17)
        parent = next(skill for skill in result.output["workspace_skills"] if skill["name"] == "commerce-travel")
        child = next(skill for skill in result.output["workspace_skills"] if skill["name"] == "railway-ticket-booking")
        self.assertEqual(parent["hierarchy_kind"], "domain_parent")
        self.assertGreaterEqual(parent["child_skill_count"], 1)
        self.assertEqual(child["parent_skill_id"], "workspace:skills/commerce-travel/SKILL.md")

    def test_workspace_skill_tool_maps_resolve_to_native_tools_or_skills(self) -> None:
        config = AgentConfig(workspace=REPO_ROOT, data_dir=REPO_ROOT / "artifacts").normalized()
        tool_names = set(default_tools(config))
        skill_names = {path.parent.name for path in (REPO_ROOT / "skills").rglob("SKILL.md")}

        for path in sorted((REPO_ROOT / "skills").rglob("SKILL.md")):
            entries = _tool_map_entries(path)
            missing = [entry for entry in entries if entry not in tool_names and entry not in skill_names]
            with self.subTest(skill=path.parent.name):
                self.assertTrue(entries, "Every workspace skill must map to native tools or referenced skills.")
                self.assertFalse(missing, f"Unresolved Tool Map entries: {missing}")


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:80]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata


def _tool_map_entries(path: Path) -> list[str]:
    entries: list[str] = []
    in_tool_map = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().lower().startswith("## tool map"):
            in_tool_map = True
            continue
        if in_tool_map and line.startswith("## "):
            break
        if not in_tool_map:
            continue
        match = re.match(r"\s*-\s+`([^`]+)`", line)
        if match:
            entries.append(match.group(1))
    return entries


if __name__ == "__main__":
    unittest.main()
