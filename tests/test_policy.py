import unittest

from humungousaur.safety.policy import PolicyEngine
from humungousaur.schemas import RiskLevel
from humungousaur.tools.base import Tool


class DummyTool(Tool):
    def execute(self, tool_input, config):
        raise NotImplementedError


class PolicyTests(unittest.TestCase):
    def test_low_risk_tool_is_allowed(self) -> None:
        tool = DummyTool("dummy", "test", RiskLevel.LOW)
        decision = PolicyEngine().evaluate(tool)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)

    def test_high_risk_tool_requires_approval(self) -> None:
        tool = DummyTool("dummy", "test", RiskLevel.HIGH)
        decision = PolicyEngine().evaluate(tool)
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

    def test_blocked_tool_is_never_allowed(self) -> None:
        tool = DummyTool("dummy", "test", RiskLevel.BLOCKED)
        decision = PolicyEngine().evaluate(tool, approved=True)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.requires_approval)


if __name__ == "__main__":
    unittest.main()
