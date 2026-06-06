import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.skill_tools import (
    AgentSkillCatalogTool,
    AgentSkillImportTool,
    AgentSkillReadTool,
    AgentSkillScriptCatalogTool,
    AgentSkillScriptReadTool,
    AgentSkillScriptRunTool,
)


class SkillToolTests(unittest.TestCase):
    def test_workspace_skill_catalog_read_and_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_dir = workspace / "skills" / "gateway"
            skill_dir.mkdir(parents=True)
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: gateway-test\n"
                "description: Test gateway workflow.\n"
                "---\n"
                "# Gateway Test\n\nUse structured channel metadata.\n",
                encoding="utf-8",
            )
            (scripts_dir / "status.py").write_text(
                "# humungousaur-skill-script: "
                '{"name":"gateway-status","description":"Return a structured gateway status payload.",'
                '"input_schema":{"type":"object","properties":{"message":{"type":"string"}}}}\n'
                "from __future__ import annotations\n"
                "import json\n"
                "import sys\n\n"
                "envelope = json.loads(sys.stdin.read() or '{}')\n"
                "message = envelope.get('input', {}).get('message', '')\n"
                "print(json.dumps({'ok': True, 'message': message, 'workspace': envelope.get('workspace')}))\n",
                encoding="utf-8",
            )
            config = AgentConfig(workspace=workspace, data_dir=workspace / "artifacts").normalized()

            catalog = AgentSkillCatalogTool().execute({"source": "workspace"}, config)
            skill_id = catalog.output["workspace_skills"][0]["skill_id"]
            read = AgentSkillReadTool().execute({"skill_id": skill_id}, config)
            imported = AgentSkillImportTool().execute({"skill_ids": [skill_id], "reason": "test"}, config)
            memory = AgentSkillCatalogTool().execute({"source": "memory"}, config)
            script_catalog = AgentSkillScriptCatalogTool().execute({"skill_id": skill_id}, config)
            script_id = script_catalog.output["scripts"][0]["script_id"]
            script_read = AgentSkillScriptReadTool().execute({"script_id": script_id}, config)
            script_run = AgentSkillScriptRunTool().execute(
                {"script_id": script_id, "input": {"message": "hello"}, "reason": "test native skill capability"},
                config,
            )

        self.assertEqual(catalog.status, ActionStatus.SUCCEEDED)
        self.assertEqual(catalog.output["workspace_skills"][0]["name"], "gateway-test")
        self.assertEqual(catalog.output["workspace_skills"][0]["script_count"], 1)
        self.assertIn("Use structured channel metadata", read.output["content"])
        self.assertEqual(imported.status, ActionStatus.SUCCEEDED)
        self.assertEqual(imported.output["imported_skills"][0]["name"], "Workspace: gateway-test")
        self.assertEqual(memory.output["memory_skills"][0]["name"], "Workspace: gateway-test")
        self.assertEqual(script_catalog.status, ActionStatus.SUCCEEDED)
        self.assertEqual(script_catalog.output["scripts"][0]["name"], "gateway-status")
        self.assertEqual(script_catalog.output["scripts"][0]["skill_id"], skill_id)
        self.assertEqual(script_read.status, ActionStatus.SUCCEEDED)
        self.assertIn("Return a structured gateway status payload", script_read.output["content"])
        self.assertEqual(script_run.status, ActionStatus.SUCCEEDED)
        self.assertTrue(script_run.output["json"]["ok"])
        self.assertEqual(script_run.output["json"]["message"], "hello")


if __name__ == "__main__":
    unittest.main()
