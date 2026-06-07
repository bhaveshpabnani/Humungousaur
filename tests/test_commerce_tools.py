import json
import tempfile
import unittest
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus
from humungousaur.tools.commerce_tools import (
    PurchaseIntentInspectTool,
    PurchaseIntentPrepareTool,
    ShoppingComparisonCreateTool,
    ShoppingComparisonInspectTool,
)


class CommerceToolTests(unittest.TestCase):
    def test_shopping_comparison_create_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            created = ShoppingComparisonCreateTool().execute(
                {
                    "filename": "laptop-comparison.md",
                    "title": "Laptop Comparison",
                    "budget": "$1200",
                    "region": "US",
                    "decision_criteria": ["16 GB RAM", "good return policy"],
                    "products": [
                        {"name": "Laptop A", "seller": "Example Store", "price": "$999", "availability": "in stock", "return_terms": "30 days", "pros": ["light"], "cons": ["limited ports"], "source_ref": "fixture"}
                    ],
                    "recommendation": "Laptop A is acceptable if port count is not critical.",
                    "risks": ["Live price was not checked."],
                    "source_refs": ["fixture"],
                    "reason": "Verify native shopping comparison artifact.",
                },
                config,
            )
            inspected = ShoppingComparisonInspectTool().execute({"path": created.output["path"]}, config)
            metadata = json.loads(Path(created.output["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(created.status, ActionStatus.SUCCEEDED)
        self.assertEqual(created.output["product_count"], 1)
        self.assertEqual(created.output["purchase_status"], "research_only_not_purchased")
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["risk_count"], 1)
        self.assertIn("No cart", metadata["safety_note"])

    def test_purchase_intent_prepare_and_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            prepared = PurchaseIntentPrepareTool().execute(
                {
                    "filename": "cart-review.md",
                    "intent_type": "cart_review",
                    "seller": "Example Store",
                    "items": [{"name": "Laptop A", "quantity": "1", "price": "$999", "seller": "Example Store", "source_ref": "fixture"}],
                    "total": "$999 before tax",
                    "return_terms": "30 days",
                    "checks": [{"name": "Seller verified", "status": "not_verified", "evidence": "fixture only"}],
                    "reason": "Verify native purchase intent artifact.",
                },
                config,
            )
            inspected = PurchaseIntentInspectTool().execute({"path": prepared.output["path"]}, config)

        self.assertEqual(prepared.status, ActionStatus.SUCCEEDED)
        self.assertEqual(prepared.output["purchase_status"], "prepared_not_purchased")
        self.assertTrue(prepared.output["approval_required"])
        self.assertEqual(inspected.status, ActionStatus.SUCCEEDED)
        self.assertEqual(inspected.output["item_count"], 1)
        self.assertEqual(inspected.output["check_count"], 1)

    def test_purchase_intent_requires_item_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()

            result = PurchaseIntentPrepareTool().execute(
                {"intent_type": "purchase", "items": [{"price": "$10"}], "reason": "Verify validation."},
                config,
            )

        self.assertEqual(result.status, ActionStatus.FAILED)
        self.assertIn("requires a name", result.summary)


if __name__ == "__main__":
    unittest.main()
