from __future__ import annotations

import re
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.tools.skill_tools import AgentSkillCatalogTool


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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

    def test_skill_catalog_can_list_more_than_one_hundred_workspace_skills(self) -> None:
        config = AgentConfig(workspace=REPO_ROOT, data_dir=REPO_ROOT / "artifacts").normalized()
        schema = AgentSkillCatalogTool().input_schema

        self.assertEqual(schema["properties"]["limit"]["maximum"], 300)

        result = AgentSkillCatalogTool().execute({"source": "workspace", "limit": 300}, config)

        self.assertEqual(result.output["source"], "workspace")
        self.assertGreaterEqual(len(result.output["workspace_skills"]), 17)


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


if __name__ == "__main__":
    unittest.main()
