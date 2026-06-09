from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema
from humungousaur.tools.domain_capabilities import build_domain_capability_tools


MAX_COMMERCE_ITEMS = 200
MAX_TEXT_CHARS = 20_000


class ShoppingComparisonCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="shopping_comparison_create",
            description=(
                "Create a local shopping comparison artifact from explicit product evidence, criteria, prices, sellers, "
                "risks, and recommendation notes. This does not add to cart, contact sellers, or purchase."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/commerce/comparisons."},
                    "title": {"type": "string"},
                    "budget": {"type": "string"},
                    "region": {"type": "string"},
                    "decision_criteria": {"type": "array", "items": {"type": "string"}},
                    "products": {"type": "array", "items": {"type": "object"}},
                    "recommendation": {"type": "string"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "evidence_checked_at": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["title", "products", "reason"],
            ),
            capability_group="commerce",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Shopping comparison title and reason are required.")
        try:
            products = _products(tool_input.get("products"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not products:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one product is required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"shopping-comparison-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "commerce" / "comparisons" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Shopping comparison path is outside allowed write roots.")
        artifact = _comparison_artifact(tool_input, title=title, products=products, reason=reason, markdown_path=markdown_path)
        markdown = _render_comparison(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create shopping comparison {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created shopping comparison artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "comparison_id": artifact["comparison_id"],
                "product_count": len(artifact["products"]),
                "purchase_status": artifact["purchase_status"],
                "source": "shopping_comparison_create",
            },
        )


class ShoppingComparisonInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="shopping_comparison_inspect",
            description="Inspect a local shopping comparison artifact for product count, risk count, recommendation, purchase status, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute comparison markdown path."}}, required=["path"]),
            capability_group="commerce",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="commerce/comparisons", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Shopping comparison path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Shopping comparison file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected shopping comparison artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "comparison_id": metadata.get("comparison_id", ""),
                "title": metadata.get("title", ""),
                "product_count": len(metadata.get("products", [])) if isinstance(metadata.get("products"), list) else 0,
                "risk_count": len(metadata.get("risks", [])) if isinstance(metadata.get("risks"), list) else 0,
                "purchase_status": metadata.get("purchase_status", ""),
                "preview": text[:4000],
                "source": "shopping_comparison_inspect",
            },
        )


class PurchaseIntentPrepareTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="purchase_intent_prepare",
            description=(
                "Prepare a local cart, checkout, purchase, subscription, refund, or payment-review intent artifact. "
                "This requires approval for any live execution and never stores payment credentials."
            ),
            risk_level=RiskLevel.HIGH,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/commerce/purchase_intents."},
                    "intent_type": {"type": "string", "enum": ["cart_review", "checkout_review", "purchase", "subscription", "refund", "cancellation", "payment_review"]},
                    "seller": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "object"}},
                    "total": {"type": "string"},
                    "taxes": {"type": "string"},
                    "shipping": {"type": "string"},
                    "return_terms": {"type": "string"},
                    "recurring_terms": {"type": "string"},
                    "payment_method_label": {"type": "string"},
                    "shipping_address_label": {"type": "string"},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "checks": {"type": "array", "items": {"type": "object"}},
                    "approval_note": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["intent_type", "items", "reason"],
            ),
            capability_group="commerce",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        intent_type = str(tool_input.get("intent_type") or "").strip()
        reason = str(tool_input.get("reason") or "").strip()
        if not intent_type or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Purchase intent type and reason are required.")
        try:
            items = _purchase_items(tool_input.get("items"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not items:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one purchase item is required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"purchase-intent-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "commerce" / "purchase_intents" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Purchase intent path is outside allowed write roots.")
        artifact = _purchase_artifact(tool_input, intent_type=intent_type, items=items, reason=reason, markdown_path=markdown_path)
        markdown = _render_purchase_intent(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would prepare purchase intent {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Prepared purchase intent artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "purchase_intent_id": artifact["purchase_intent_id"],
                "intent_type": artifact["intent_type"],
                "item_count": len(artifact["items"]),
                "purchase_status": artifact["purchase_status"],
                "approval_required": artifact["approval_required"],
                "source": "purchase_intent_prepare",
            },
        )


class PurchaseIntentInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="purchase_intent_inspect",
            description="Inspect a local purchase/payment intent artifact for item count, approval status, checks, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute purchase-intent markdown path."}}, required=["path"]),
            capability_group="commerce",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="commerce/purchase_intents", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Purchase intent path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Purchase intent file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected purchase intent artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "purchase_intent_id": metadata.get("purchase_intent_id", ""),
                "intent_type": metadata.get("intent_type", ""),
                "item_count": len(metadata.get("items", [])) if isinstance(metadata.get("items"), list) else 0,
                "check_count": len(metadata.get("checks", [])) if isinstance(metadata.get("checks"), list) else 0,
                "purchase_status": metadata.get("purchase_status", ""),
                "approval_required": bool(metadata.get("approval_required", True)),
                "preview": text[:4000],
                "source": "purchase_intent_inspect",
            },
        )


def default_commerce_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        ShoppingComparisonCreateTool(),
        ShoppingComparisonInspectTool(),
        PurchaseIntentPrepareTool(),
        PurchaseIntentInspectTool(),
    ]
    registry = {tool.name: tool for tool in tools}
    registry.update(build_domain_capability_tools("commerce"))
    return registry


def _comparison_artifact(tool_input: dict[str, Any], *, title: str, products: list[dict[str, Any]], reason: str, markdown_path: Path) -> dict[str, Any]:
    return {
        "comparison_id": f"shopping-comparison-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "budget": _bounded_text(tool_input.get("budget")),
        "region": _bounded_text(tool_input.get("region")),
        "decision_criteria": _string_list(tool_input.get("decision_criteria"), limit=MAX_COMMERCE_ITEMS),
        "products": products,
        "recommendation": _bounded_text(tool_input.get("recommendation")),
        "risks": _string_list(tool_input.get("risks"), limit=MAX_COMMERCE_ITEMS),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_COMMERCE_ITEMS),
        "evidence_checked_at": _bounded_text(tool_input.get("evidence_checked_at")) or datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "path": str(markdown_path),
        "purchase_status": "research_only_not_purchased",
        "safety_note": "Shopping research only. No cart, checkout, payment, order, or seller contact was performed.",
    }


def _purchase_artifact(tool_input: dict[str, Any], *, intent_type: str, items: list[dict[str, str]], reason: str, markdown_path: Path) -> dict[str, Any]:
    checks = _checks(tool_input.get("checks"))
    if not checks:
        checks = [
            {"name": "Seller verified", "status": "not_verified", "evidence": ""},
            {"name": "Final total verified", "status": "not_verified", "evidence": ""},
            {"name": "Return/recurring terms reviewed", "status": "not_verified", "evidence": ""},
        ]
    return {
        "purchase_intent_id": f"purchase-intent-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "intent_type": intent_type,
        "seller": _bounded_text(tool_input.get("seller")),
        "items": items,
        "total": _bounded_text(tool_input.get("total")),
        "taxes": _bounded_text(tool_input.get("taxes")),
        "shipping": _bounded_text(tool_input.get("shipping")),
        "return_terms": _bounded_text(tool_input.get("return_terms")),
        "recurring_terms": _bounded_text(tool_input.get("recurring_terms")),
        "payment_method_label": _bounded_text(tool_input.get("payment_method_label")),
        "shipping_address_label": _bounded_text(tool_input.get("shipping_address_label")),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_COMMERCE_ITEMS),
        "checks": checks,
        "approval_note": _bounded_text(tool_input.get("approval_note")),
        "reason": reason,
        "path": str(markdown_path),
        "purchase_status": "prepared_not_purchased",
        "approval_required": True,
        "credential_storage": "payment_credentials_not_stored",
        "safety_note": "Prepared review artifact only. No purchase, payment, checkout submission, subscription, refund, cancellation, or seller message was executed.",
    }


def _products(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("Products must be a list.")
    products = []
    for raw in value[:MAX_COMMERCE_ITEMS]:
        if not isinstance(raw, dict):
            raise ValueError("Each product must be an object.")
        name = _bounded_text(raw.get("name"))
        if not name:
            raise ValueError("Each product requires a name.")
        products.append(
            {
                "name": name,
                "seller": _bounded_text(raw.get("seller")),
                "price": _bounded_text(raw.get("price")),
                "availability": _bounded_text(raw.get("availability")),
                "shipping": _bounded_text(raw.get("shipping")),
                "return_terms": _bounded_text(raw.get("return_terms")),
                "warranty": _bounded_text(raw.get("warranty")),
                "pros": "; ".join(_string_list(raw.get("pros"), limit=30)),
                "cons": "; ".join(_string_list(raw.get("cons"), limit=30)),
                "source_ref": _bounded_text(raw.get("source_ref")),
                "notes": _bounded_text(raw.get("notes")),
            }
        )
    return products


def _purchase_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("Purchase items must be a list.")
    items = []
    for raw in value[:MAX_COMMERCE_ITEMS]:
        if not isinstance(raw, dict):
            raise ValueError("Each purchase item must be an object.")
        name = _bounded_text(raw.get("name"))
        if not name:
            raise ValueError("Each purchase item requires a name.")
        items.append(
            {
                "name": name,
                "quantity": _bounded_text(raw.get("quantity") or "1"),
                "price": _bounded_text(raw.get("price")),
                "seller": _bounded_text(raw.get("seller")),
                "source_ref": _bounded_text(raw.get("source_ref")),
                "notes": _bounded_text(raw.get("notes")),
            }
        )
    return items


def _checks(value: Any) -> list[dict[str, str]]:
    checks = []
    for raw in _bounded_list(value, MAX_COMMERCE_ITEMS):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name"))
        if not name:
            continue
        checks.append({"name": name, "status": _bounded_text(raw.get("status") or "unknown"), "evidence": _bounded_text(raw.get("evidence"))})
    return checks


def _render_comparison(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['title']}", "", f"Purchase status: {artifact['purchase_status']}", f"Evidence checked at: {artifact['evidence_checked_at']}", ""]
    for key in ("budget", "region"):
        if artifact[key]:
            lines.append(f"{key.title()}: {artifact[key]}")
    lines.append("")
    _append_list(lines, "Decision Criteria", artifact["decision_criteria"])
    lines.extend(["## Products", "", "| Name | Seller | Price | Availability | Shipping | Returns | Pros | Cons | Source |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"])
    for product in artifact["products"]:
        lines.append(
            f"| {product['name']} | {product['seller']} | {product['price']} | {product['availability']} | {product['shipping']} | {product['return_terms']} | {product['pros']} | {product['cons']} | {product['source_ref']} |"
        )
    lines.append("")
    if artifact["recommendation"]:
        lines.extend(["## Recommendation", "", artifact["recommendation"], ""])
    _append_list(lines, "Risks", artifact["risks"])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _render_purchase_intent(artifact: dict[str, Any]) -> str:
    lines = [f"# {artifact['intent_type'].replace('_', ' ').title()}", "", f"Purchase status: {artifact['purchase_status']}", f"Approval required: {artifact['approval_required']}", f"Credential storage: {artifact['credential_storage']}", ""]
    for key in ("seller", "total", "taxes", "shipping", "return_terms", "recurring_terms", "payment_method_label", "shipping_address_label"):
        if artifact[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {artifact[key]}")
    lines.append("")
    lines.extend(["## Items", "", "| Name | Quantity | Price | Seller | Source | Notes |", "| --- | --- | --- | --- | --- | --- |"])
    for item in artifact["items"]:
        lines.append(f"| {item['name']} | {item['quantity']} | {item['price']} | {item['seller']} | {item['source_ref']} | {item['notes']} |")
    lines.append("")
    if artifact["checks"]:
        lines.extend(["## Checks", "", "| Check | Status | Evidence |", "| --- | --- | --- |"])
        for check in artifact["checks"]:
            lines.append(f"| {check['name']} | {check['status']} | {check['evidence']} |")
        lines.append("")
    if artifact["approval_note"]:
        lines.extend(["## Approval Note", "", artifact["approval_note"], ""])
    _append_list(lines, "Source References", artifact["source_refs"])
    lines.extend(["## Safety Note", "", artifact["safety_note"], "", f"Created: {artifact['created_at']}"])
    return "\n".join(lines) + "\n"


def _append_list(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _bounded_text(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_TEXT_CHARS]


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, limit)]


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _resolve_allowed_path(config: AgentConfig, raw_path: str, *, subdir: str, suffix: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = config.workspace / path
        if not path.exists():
            data_path = config.data_dir / raw_path
            if data_path.exists():
                path = data_path
            else:
                artifact_path = config.data_dir / subdir / Path(raw_path).name
                if artifact_path.exists():
                    path = artifact_path
    if not path.suffix:
        path = path.with_suffix(suffix)
    return path.resolve()


def _load_sidecar(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _safe_filename(value: str, suffix: str) -> str:
    name = Path(value).name.strip() or f"artifact{suffix}"
    if not name.lower().endswith(suffix):
        name += suffix
    stem = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in Path(name).stem).strip(".-")
    return f"{stem or 'artifact'}{suffix}"


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)
