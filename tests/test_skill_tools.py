import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.skill_tools import AgentSkillCatalogTool, AgentSkillImportTool, AgentSkillReadTool


class SkillToolTests(unittest.TestCase):
    def test_workspace_skill_catalog_read_and_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_dir = workspace / "skills" / "gateway"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: gateway-test\n"
                "description: Test gateway workflow.\n"
                "---\n"
                "# Gateway Test\n\nUse structured channel metadata.\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            catalog = AgentSkillCatalogTool().execute({"source": "workspace"}, config)
            skill_id = catalog.output["workspace_skills"][0]["skill_id"]
            read = AgentSkillReadTool().execute({"skill_id": skill_id}, config)
            imported = AgentSkillImportTool().execute({"skill_ids": [skill_id], "reason": "test"}, config)
            memory = AgentSkillCatalogTool().execute({"source": "memory"}, config)

        self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
        self.assertEqual(catalog.output["workspace_skills"][0]["name"], "gateway-test")
        self.assertIn("Use structured channel metadata", read.output["content"])
        self.assertEqual(imported.status, ActionStatus.SUCCEEDED)
        self.assertEqual(imported.output["imported_skills"][0]["name"], "Workspace: gateway-test")
        self.assertEqual(memory.output["memory_skills"][0]["name"], "Workspace: gateway-test")


if __name__ == "__main__":
    unittest.main()
