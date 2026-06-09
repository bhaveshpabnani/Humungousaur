from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import socket
import ssl
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from humungousaur.config import AgentConfig
from humungousaur.schemas import ActionStatus, RiskLevel, ToolResult
from humungousaur.tools.base import Tool, object_input_schema


MAX_TRAVEL_ITEMS = 200
MAX_TEXT_CHARS = 20_000
RAIL_LOOKUP_TIMEOUT_SECONDS = 20
RAIL_LOOKUP_USER_AGENT = "Mozilla/5.0 (compatible; HumungousaurRailLookup/1.0; +https://example.local)"


class RailRouteAvailabilityLookupTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="rail_route_availability_lookup",
            description=(
                "Look up Indian railway route/date/class availability from a concrete route source URL discovered by search or browser evidence. "
                "Currently supports ixigo route pages by reading the route train list and train-specific availability pages. "
                "Use this for rail availability questions after a route page URL is known; it returns confirmed available, RAC, waitlisted, unavailable, and unresolved options with source URLs. "
                "This is read-only and does not book tickets, enter passenger data, solve captchas, log in, pay, or prepare a booking intent."
            ),
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema(
                {
                    "route_page_url": {"type": "string", "description": "Concrete route page URL, for example an ixigo route page for Nagpur to Kharagpur. If omitted, provide origin and destination so the tool can construct the supported ixigo route URL."},
                    "journey_date": {"type": "string", "description": "Journey date as YYYY-MM-DD when possible."},
                    "class_code": {"type": "string", "description": "Railway class code such as SL, 3A, 2A, 1A, CC, or 2S."},
                    "origin": {"type": "string", "description": "Origin city or station name/code used for output context."},
                    "destination": {"type": "string", "description": "Destination city or station name/code used for output context."},
                    "max_trains": {"type": "integer", "minimum": 1, "maximum": 30},
                    "reason": {"type": "string"},
                },
                required=["journey_date", "reason"],
            ),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        del config
        route_page_url = str(tool_input.get("route_page_url") or "").strip()
        journey_date = str(tool_input.get("journey_date") or "").strip()
        class_code = (str(tool_input.get("class_code") or "SL").strip().upper() or "SL")[:12]
        origin = _bounded_text(tool_input.get("origin"))
        destination = _bounded_text(tool_input.get("destination"))
        reason = str(tool_input.get("reason") or "").strip()
        try:
            max_trains = max(1, min(30, int(tool_input.get("max_trains") or 20)))
        except (TypeError, ValueError):
            max_trains = 20
        if not route_page_url and origin and destination:
            route_page_url = _ixigo_route_url(origin, destination)
        if not route_page_url or not journey_date or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Journey date and reason are required, plus either a route page URL or origin and destination.")
        parsed = urlparse(route_page_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Route page URL must be an http(s) URL.")
        if "ixigo.com" not in parsed.netloc.lower():
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Rail availability lookup currently supports ixigo route pages only.")
        try:
            date_label = _ixigo_date_label(journey_date)
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        try:
            route_html = _http_get_text(route_page_url)
        except RuntimeError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, f"Could not fetch route page: {exc}", error=str(exc))
        trains = _parse_ixigo_route_trains(route_html)[:max_trains]
        if not trains:
            return ToolResult(
                self.name,
                ActionStatus.FAILED,
                self.risk_level,
                "No train numbers could be extracted from the route page.",
                {"source": "rail_route_availability_lookup", "route_page_url": route_page_url},
            )
        all_options: list[dict[str, Any]] = []
        for train in trains:
            train_url = f"https://www.ixigo.com/trains/{train['train_no']}/seat-availability"
            try:
                train_html = _http_get_text(train_url)
                status_record = _parse_ixigo_train_availability(train_html, date_label=date_label, class_code=class_code)
            except RuntimeError as exc:
                status_record = {
                    "status": "unresolved",
                    "status_text": "unresolved",
                    "category": "unresolved",
                    "evidence": f"Could not fetch train availability page: {exc}",
                }
            option = {
                "train_no": train["train_no"],
                "train_name": train["train_name"],
                "status": status_record["status"],
                "status_text": status_record["status_text"],
                "category": status_record["category"],
                "date_label": date_label,
                "class_code": class_code,
                "url": train_url,
                "evidence": status_record.get("evidence", ""),
            }
            all_options.append(option)
        available = [item for item in all_options if item["category"] == "available"]
        rac = [item for item in all_options if item["category"] == "rac"]
        waitlisted = [item for item in all_options if item["category"] == "waitlisted"]
        unavailable = [item for item in all_options if item["category"] == "unavailable"]
        unresolved = [item for item in all_options if item["category"] == "unresolved"]
        summary = _rail_lookup_summary(available, rac=rac, waitlisted=waitlisted, unavailable=unavailable, unresolved=unresolved, class_code=class_code, date_label=date_label)
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            summary,
            {
                "source": "rail_route_availability_lookup",
                "provider": "ixigo",
                "route_page_url": route_page_url,
                "origin": origin,
                "destination": destination,
                "journey_date": journey_date,
                "date_label": date_label,
                "class_code": class_code,
                "train_count": len(all_options),
                "available": available,
                "rac": rac,
                "waitlisted": waitlisted,
                "unavailable": unavailable,
                "unresolved": unresolved,
                "all_options": all_options,
                "answer_summary": summary,
                "evidence_checked_at": datetime.now(timezone.utc).isoformat(),
            },
        )


class TravelPlanCreateTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="travel_plan_create",
            description=(
                "Create a local travel, route, commute, or itinerary planning artifact from explicit evidence. "
                "Stores places, route options, itinerary days, constraints, source refs, uncertainties, and approval boundaries. "
                "This does not book, pay, cancel, contact venues, or claim live routing without evidence."
            ),
            risk_level=RiskLevel.MEDIUM,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/travel/plans."},
                    "title": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "date_range": {"type": "string"},
                    "travelers": {"type": "string"},
                    "budget": {"type": "string"},
                    "preferences": {"type": "array", "items": {"type": "string"}},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "places": {"type": "array", "items": {"type": "object"}},
                    "route_options": {"type": "array", "items": {"type": "object"}},
                    "itinerary_days": {"type": "array", "items": {"type": "object"}},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "evidence_checked_at": {"type": "string"},
                    "uncertainties": {"type": "array", "items": {"type": "string"}},
                    "approval_boundaries": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                required=["title", "reason"],
            ),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        title = " ".join(str(tool_input.get("title") or "").split())
        reason = str(tool_input.get("reason") or "").strip()
        if not title or not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel plan title and reason are required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"travel-plan-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "travel" / "plans" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel plan path is outside allowed write roots.")
        artifact = _travel_plan(tool_input, title=title, reason=reason, markdown_path=markdown_path)
        markdown = _render_travel_plan(artifact)
        if config.dry_run:
            return ToolResult(self.name, ActionStatus.SKIPPED, self.risk_level, f"Dry run: would create travel plan {markdown_path}.", {"path": str(markdown_path), "artifact": artifact})
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Created travel plan artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "travel_plan_id": artifact["travel_plan_id"],
                "place_count": len(artifact["places"]),
                "route_option_count": len(artifact["route_options"]),
                "itinerary_day_count": len(artifact["itinerary_days"]),
                "approval_status": artifact["approval_status"],
                "source": "travel_plan_create",
            },
        )


class TravelPlanInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="travel_plan_inspect",
            description="Inspect a local travel plan artifact for routes, places, itinerary days, evidence refs, approval boundaries, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute travel plan markdown path."}}, required=["path"]),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="travel/plans", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel plan path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel plan file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected travel plan artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "travel_plan_id": metadata.get("travel_plan_id", ""),
                "title": metadata.get("title", ""),
                "origin": metadata.get("origin", ""),
                "destination": metadata.get("destination", ""),
                "place_count": len(metadata.get("places", [])) if isinstance(metadata.get("places"), list) else 0,
                "route_option_count": len(metadata.get("route_options", [])) if isinstance(metadata.get("route_options"), list) else 0,
                "itinerary_day_count": len(metadata.get("itinerary_days", [])) if isinstance(metadata.get("itinerary_days"), list) else 0,
                "uncertainty_count": len(metadata.get("uncertainties", [])) if isinstance(metadata.get("uncertainties"), list) else 0,
                "approval_status": metadata.get("approval_status", ""),
                "preview": text[:4000],
                "source": "travel_plan_inspect",
            },
        )


class TravelBookingIntentPrepareTool(Tool):
    def __init__(self) -> None:
        booking_option_schema = {
            "type": "object",
            "additionalProperties": True,
            "required": ["label"],
            "properties": {
                "option_id": {"type": "string"},
                "label": {
                    "type": "string",
                    "description": "Concrete train, flight, hotel, or travel option label from gathered evidence, not just a route/date placeholder.",
                },
                "provider": {"type": "string"},
                "number": {"type": "string"},
                "departure": {"type": "string"},
                "arrival": {"type": "string"},
                "class_or_cabin": {"type": "string"},
                "quota_or_fare_family": {"type": "string"},
                "fare": {"type": "string"},
                "availability_status": {"type": "string"},
                "source_ref": {"type": "string"},
            },
        }
        super().__init__(
            name="travel_booking_intent_prepare",
            description=(
                "Prepare a local railway, flight, or other travel-ticket booking intent from current source/browser evidence. "
                "Stores candidate options, selected option, passenger requirements, fare/availability evidence, checks, and approval boundaries. "
                "Use only after the user explicitly asks to book, proceed, or prepare a booking review artifact; do not use this to search, inspect schedules, or answer availability questions. "
                "This does not book, pay, cancel, transmit passenger data, solve captchas, or claim confirmation/PNR/ticketing."
            ),
            risk_level=RiskLevel.HIGH,
            input_schema=object_input_schema(
                {
                    "filename": {"type": "string", "description": "Output markdown filename under data_dir/travel/booking_intents."},
                    "mode": {"type": "string", "enum": ["rail", "flight", "bus", "hotel", "other"]},
                    "title": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "departure_date": {"type": "string"},
                    "return_date": {"type": "string"},
                    "travelers": {"type": "string"},
                    "passenger_requirements": {"type": "array", "items": {"type": "string"}},
                    "preferences": {"type": "array", "items": {"type": "string"}},
                    "selected_option_id": {"type": "string"},
                    "options": {"type": "array", "items": booking_option_schema},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "evidence_checked_at": {"type": "string"},
                    "checks": {"type": "array", "items": {"type": "object"}},
                    "uncertainties": {"type": "array", "items": {"type": "string"}},
                    "approval_note": {"type": "string"},
                    "reason": {"type": "string"},
                },
                required=["mode", "options", "reason"],
            ),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        mode = str(tool_input.get("mode") or "").strip().lower()
        reason = str(tool_input.get("reason") or "").strip()
        if mode not in {"rail", "flight", "bus", "hotel", "other"}:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel booking mode must be rail, flight, bus, hotel, or other.")
        if not reason:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel booking intent reason is required.")
        try:
            options = _booking_options(tool_input.get("options"))
        except ValueError as exc:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, str(exc), error=str(exc))
        if not options:
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "At least one travel booking option is required.")
        filename = _safe_filename(str(tool_input.get("filename") or f"travel-booking-intent-{uuid4().hex[:8]}.md"), ".md")
        markdown_path = (normalized.data_dir / "travel" / "booking_intents" / filename).resolve()
        if not _is_within(markdown_path, normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel booking intent path is outside allowed write roots.")
        artifact = _booking_intent(tool_input, mode=mode, options=options, reason=reason, markdown_path=markdown_path)
        markdown = _render_booking_intent(artifact)
        if config.dry_run:
            return ToolResult(
                self.name,
                ActionStatus.SKIPPED,
                self.risk_level,
                f"Dry run: would prepare travel booking intent {markdown_path}.",
                {"path": str(markdown_path), "artifact": artifact},
            )
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        metadata_path = markdown_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Prepared travel booking intent artifact {markdown_path}.",
            {
                "path": str(markdown_path),
                "metadata_path": str(metadata_path),
                "travel_booking_intent_id": artifact["travel_booking_intent_id"],
                "mode": artifact["mode"],
                "option_count": len(artifact["options"]),
                "booking_status": artifact["booking_status"],
                "approval_required": artifact["approval_required"],
                "source": "travel_booking_intent_prepare",
            },
        )


class TravelBookingIntentInspectTool(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="travel_booking_intent_inspect",
            description="Inspect a local travel booking intent artifact for mode, options, selected option, checks, approval status, and preview text.",
            risk_level=RiskLevel.LOW,
            input_schema=object_input_schema({"path": {"type": "string", "description": "Workspace-relative or allowed absolute booking-intent markdown path."}}, required=["path"]),
            capability_group="travel",
        )

    def execute(self, tool_input: dict[str, Any], config: AgentConfig) -> ToolResult:
        normalized = config.normalized()
        path = _resolve_allowed_path(normalized, str(tool_input.get("path") or ""), subdir="travel/booking_intents", suffix=".md")
        if not _is_within(path, normalized.allowed_read_roots + normalized.allowed_write_roots):
            return ToolResult(self.name, ActionStatus.BLOCKED, self.risk_level, "Travel booking intent path is outside allowed roots.")
        if not path.exists() or path.suffix.lower() != ".md":
            return ToolResult(self.name, ActionStatus.FAILED, self.risk_level, "Travel booking intent file does not exist.")
        metadata = _load_sidecar(path.with_suffix(".json"))
        text = path.read_text(encoding="utf-8")
        return ToolResult(
            self.name,
            ActionStatus.SUCCEEDED,
            self.risk_level,
            f"Inspected travel booking intent artifact {path}.",
            {
                "path": str(path),
                "metadata_path": str(path.with_suffix(".json")) if path.with_suffix(".json").exists() else "",
                "travel_booking_intent_id": metadata.get("travel_booking_intent_id", ""),
                "mode": metadata.get("mode", ""),
                "title": metadata.get("title", ""),
                "selected_option_id": metadata.get("selected_option_id", ""),
                "option_count": len(metadata.get("options", [])) if isinstance(metadata.get("options"), list) else 0,
                "check_count": len(metadata.get("checks", [])) if isinstance(metadata.get("checks"), list) else 0,
                "booking_status": metadata.get("booking_status", ""),
                "approval_required": bool(metadata.get("approval_required", True)),
                "preview": text[:4000],
                "source": "travel_booking_intent_inspect",
            },
        )


def default_travel_tools() -> dict[str, Tool]:
    tools: list[Tool] = [
        RailRouteAvailabilityLookupTool(),
        TravelPlanCreateTool(),
        TravelPlanInspectTool(),
        TravelBookingIntentPrepareTool(),
        TravelBookingIntentInspectTool(),
    ]
    return {tool.name: tool for tool in tools}


def _http_get_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": RAIL_LOOKUP_USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with _open_url_with_dns_fallback(request) as response:
            content_type = response.headers.get("content-type", "")
            charset = "utf-8"
            match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
            if match:
                charset = match.group(1)
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc


def _open_url_with_dns_fallback(request: Request):
    try:
        return urlopen(request, timeout=RAIL_LOOKUP_TIMEOUT_SECONDS, context=_ssl_context())
    except URLError as exc:
        if not _is_dns_resolution_error(exc):
            raise
        host = urlparse(request.full_url).hostname or ""
        resolved_ip = _resolve_with_public_dns(host)
        if not resolved_ip:
            raise
        original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(node, port, family=0, type=0, proto=0, flags=0):
            if str(node).lower() == host.lower():
                return original_getaddrinfo(resolved_ip, port, family, type, proto, flags)
            return original_getaddrinfo(node, port, family, type, proto, flags)

        socket.getaddrinfo = patched_getaddrinfo
        try:
            return urlopen(request, timeout=RAIL_LOOKUP_TIMEOUT_SECONDS, context=_ssl_context())
        finally:
            socket.getaddrinfo = original_getaddrinfo


def _is_dns_resolution_error(exc: URLError) -> bool:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, socket.gaierror):
        return True
    return "nodename nor servname provided" in str(exc).lower()


def _resolve_with_public_dns(hostname: str) -> str:
    if not hostname:
        return ""
    try:
        completed = subprocess.run(["dig", "+short", hostname, "@1.1.1.1"], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in completed.stdout.splitlines():
        candidate = line.strip()
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", candidate):
            return candidate
    return ""


def _ixigo_route_url(origin: str, destination: str) -> str:
    return f"https://www.ixigo.com/by-train-rail/{_ixigo_slug(origin)}-to-{_ixigo_slug(destination)}-by-train"


def _ixigo_slug(value: str) -> str:
    clean = re.sub(r"\([^)]*\)", " ", value.lower())
    clean = re.sub(r"[^a-z0-9]+", "-", clean)
    return clean.strip("-")


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _ixigo_date_label(value: str) -> str:
    clean = " ".join(str(value or "").split())
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(clean[:10], fmt)
            return parsed.strftime("%a, %d %b")
        except ValueError:
            continue
    raise ValueError("Journey date must be a recognizable full date, preferably YYYY-MM-DD.")


def _parse_ixigo_route_trains(page_html: str) -> list[dict[str, str]]:
    text_trains = _parse_ixigo_visible_route_trains(page_html)
    if text_trains:
        return text_trains
    trains: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'href=["\'](?P<href>[^"\']*/trains/route-(?P<number>\d{5})-(?P<slug>[^"\']+?))["\']', page_html, flags=re.IGNORECASE):
        train_no = match.group("number")
        if train_no in seen:
            continue
        train_name = _title_from_slug(match.group("slug"))
        trains.append({"train_no": train_no, "train_name": train_name})
        seen.add(train_no)
    if trains:
        return trains
    text = _visible_text(page_html)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not re.fullmatch(r"\d{5}", line):
            continue
        train_no = line
        if train_no in seen:
            continue
        name = ""
        for candidate in lines[index + 1 : index + 5]:
            if re.fullmatch(r"\d{1,2}:\d{2}", candidate) or candidate.lower().startswith("runs on"):
                break
            if re.search(r"[A-Za-z]", candidate):
                name = candidate
                break
        trains.append({"train_no": train_no, "train_name": _bounded_text(name) or train_no})
        seen.add(train_no)
    return trains


def _parse_ixigo_visible_route_trains(page_html: str) -> list[dict[str, str]]:
    text = _visible_text(page_html)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    start = 0
    for index, line in enumerate(lines):
        if line.lower() == "trains found between":
            start = index
            break
    end = len(lines)
    for index, line in enumerate(lines[start:], start=start):
        if line.lower().startswith("why book "):
            end = index
            break
    trains: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, line in enumerate(lines[start:end]):
        if not re.fullmatch(r"\d{5}", line):
            continue
        absolute_index = start + index
        if absolute_index > 0 and lines[absolute_index - 1] == "(":
            continue
        train_no = line
        if train_no in seen:
            continue
        name = ""
        for candidate in lines[absolute_index + 1 : min(end, absolute_index + 5)]:
            if candidate == "(" or candidate.lower() in {"runs on", "running status)"}:
                break
            if re.search(r"[A-Za-z]", candidate):
                name = candidate
                break
        if name:
            trains.append({"train_no": train_no, "train_name": _bounded_text(name)})
            seen.add(train_no)
    return trains


def _parse_ixigo_train_availability(page_html: str, *, date_label: str, class_code: str) -> dict[str, str]:
    text = _visible_text(page_html)
    class_supported = _ixigo_class_supported(text, class_code)
    if not class_supported:
        return {
            "status": "class_not_listed",
            "status_text": "class_not_listed",
            "category": "unresolved",
            "evidence": f"{class_code} was not visible in the class list on the train availability page.",
        }
    date_index = text.find(date_label)
    if date_index < 0:
        return {
            "status": "not_listed",
            "status_text": "not_listed",
            "category": "unresolved",
            "evidence": f"{date_label} was not visible on the train availability page.",
        }
    lines = [line.strip() for line in text[date_index:].splitlines() if line.strip()]
    status_line = ""
    for line in lines[1:12]:
        normalized = _normalize_status_text(line)
        if not normalized or normalized.lower().startswith(("updated", "at ", "check ", "share ", "book ")):
            continue
        if _classify_rail_status(normalized) != "unresolved" or normalized.upper() in {"NA", "N/A"}:
            status_line = normalized
            break
    if not status_line and len(lines) > 1:
        status_line = _normalize_status_text(lines[1])
    category = _classify_rail_status(status_line)
    evidence = " | ".join(lines[: min(len(lines), 5)])
    return {
        "status": status_line or "unresolved",
        "status_text": status_line or "unresolved",
        "category": category,
        "evidence": evidence[:1000],
    }


def _visible_text(page_html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|svg|noscript).*?</\1>", "\n", page_html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6]|section|article|a|button|span)>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", "\n", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def _ixigo_class_supported(text: str, class_code: str) -> bool:
    wanted = class_code.strip().upper()
    if not wanted:
        return True
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(wanted)}(?![A-Z0-9])", text.upper()))


def _normalize_status_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().upper())


def _classify_rail_status(status: str) -> str:
    normalized = _normalize_status_text(status)
    if not normalized:
        return "unresolved"
    if normalized.startswith("AVL") or normalized.startswith("AVAILABLE"):
        return "available"
    if normalized.startswith("RAC"):
        return "rac"
    if normalized.startswith("WL") or "WAITLIST" in normalized:
        return "waitlisted"
    if normalized in {"NA", "N/A"} or normalized.startswith(("REGRET", "NOTAVAILABLE", "CANCELLED")):
        return "unavailable"
    return "unresolved"


def _title_from_slug(value: str) -> str:
    clean = re.sub(r"[-_]+", " ", value.split("?")[0]).strip()
    clean = re.sub(r"\b\d{5}\b", "", clean).strip()
    return clean.title() or "Unknown Train"


def _rail_lookup_summary(
    available: list[dict[str, Any]],
    *,
    rac: list[dict[str, Any]],
    waitlisted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
    class_code: str,
    date_label: str,
) -> str:
    if available:
        labels = ", ".join(f"{item['train_no']} {item['train_name']} ({item['status']})" for item in available[:8])
        return f"{len(available)} train(s) show confirmed {class_code} availability for {date_label}: {labels}."
    parts = [f"No train showed confirmed {class_code} availability for {date_label}."]
    if rac:
        parts.append(f"{len(rac)} RAC.")
    if waitlisted:
        parts.append(f"{len(waitlisted)} waitlisted.")
    if unavailable:
        parts.append(f"{len(unavailable)} unavailable.")
    if unresolved:
        parts.append(f"{len(unresolved)} unresolved/not listed.")
    return " ".join(parts)


def _travel_plan(tool_input: dict[str, Any], *, title: str, reason: str, markdown_path: Path) -> dict[str, Any]:
    approval_boundaries = _string_list(tool_input.get("approval_boundaries"), limit=MAX_TRAVEL_ITEMS)
    if not approval_boundaries:
        approval_boundaries = [
            "No bookings, payments, cancellations, or venue contacts were performed.",
            "Changing travel facts require current source verification before action.",
        ]
    return {
        "travel_plan_id": f"travel-plan-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "origin": _bounded_text(tool_input.get("origin")),
        "destination": _bounded_text(tool_input.get("destination")),
        "date_range": _bounded_text(tool_input.get("date_range")),
        "travelers": _bounded_text(tool_input.get("travelers")),
        "budget": _bounded_text(tool_input.get("budget")),
        "preferences": _string_list(tool_input.get("preferences"), limit=MAX_TRAVEL_ITEMS),
        "constraints": _string_list(tool_input.get("constraints"), limit=MAX_TRAVEL_ITEMS),
        "places": _places(tool_input.get("places")),
        "route_options": _routes(tool_input.get("route_options")),
        "itinerary_days": _itinerary_days(tool_input.get("itinerary_days")),
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_TRAVEL_ITEMS),
        "evidence_checked_at": _bounded_text(tool_input.get("evidence_checked_at")) or datetime.now(timezone.utc).isoformat(),
        "uncertainties": _string_list(tool_input.get("uncertainties"), limit=MAX_TRAVEL_ITEMS),
        "approval_boundaries": approval_boundaries,
        "approval_status": "planning_only_not_booked",
        "reason": reason,
        "path": str(markdown_path),
        "status": "prepared_not_booked",
    }


def _places(value: Any) -> list[dict[str, str]]:
    places = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name"))
        if not name:
            continue
        places.append(
            {
                "name": name,
                "kind": _bounded_text(raw.get("kind")),
                "location": _bounded_text(raw.get("location")),
                "hours": _bounded_text(raw.get("hours")),
                "cost": _bounded_text(raw.get("cost")),
                "notes": _bounded_text(raw.get("notes")),
                "source_ref": _bounded_text(raw.get("source_ref")),
            }
        )
    return places


def _routes(value: Any) -> list[dict[str, str]]:
    routes = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("name"))
        if not label:
            continue
        routes.append(
            {
                "label": label,
                "mode": _bounded_text(raw.get("mode")),
                "estimated_duration": _bounded_text(raw.get("estimated_duration")),
                "estimated_cost": _bounded_text(raw.get("estimated_cost")),
                "reliability": _bounded_text(raw.get("reliability")),
                "accessibility": _bounded_text(raw.get("accessibility")),
                "tradeoffs": _bounded_text(raw.get("tradeoffs")),
                "source_ref": _bounded_text(raw.get("source_ref")),
            }
        )
    return routes


def _itinerary_days(value: Any) -> list[dict[str, Any]]:
    days = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        label = _bounded_text(raw.get("label") or raw.get("date"))
        if not label:
            continue
        items = []
        for item in _bounded_list(raw.get("items"), MAX_TRAVEL_ITEMS):
            if not isinstance(item, dict):
                continue
            activity = _bounded_text(item.get("activity"))
            if activity:
                items.append(
                    {
                        "time": _bounded_text(item.get("time")),
                        "activity": activity,
                        "location": _bounded_text(item.get("location")),
                        "notes": _bounded_text(item.get("notes")),
                    }
                )
        days.append({"label": label, "summary": _bounded_text(raw.get("summary")), "items": items})
    return days


def _booking_intent(tool_input: dict[str, Any], *, mode: str, options: list[dict[str, str]], reason: str, markdown_path: Path) -> dict[str, Any]:
    checks = _booking_checks(tool_input.get("checks"))
    if not checks:
        checks = [
            {"name": "Source-visible date verified", "status": "not_verified", "evidence": ""},
            {"name": "Fare and fees verified", "status": "not_verified", "evidence": ""},
            {"name": "Availability verified", "status": "not_verified", "evidence": ""},
            {"name": "Passenger details not transmitted", "status": "verified", "evidence": "Prepared local artifact only."},
            {"name": "Payment not submitted", "status": "verified", "evidence": "Prepared local artifact only."},
        ]
    title = _bounded_text(tool_input.get("title")) or f"{mode.title()} Booking Intent"
    return {
        "travel_booking_intent_id": f"travel-booking-intent-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "title": title,
        "origin": _bounded_text(tool_input.get("origin")),
        "destination": _bounded_text(tool_input.get("destination")),
        "departure_date": _bounded_text(tool_input.get("departure_date")),
        "return_date": _bounded_text(tool_input.get("return_date")),
        "travelers": _bounded_text(tool_input.get("travelers")),
        "passenger_requirements": _string_list(tool_input.get("passenger_requirements"), limit=MAX_TRAVEL_ITEMS),
        "preferences": _string_list(tool_input.get("preferences"), limit=MAX_TRAVEL_ITEMS),
        "selected_option_id": _bounded_text(tool_input.get("selected_option_id")),
        "options": options,
        "source_refs": _string_list(tool_input.get("source_refs"), limit=MAX_TRAVEL_ITEMS),
        "evidence_checked_at": _bounded_text(tool_input.get("evidence_checked_at")) or datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "uncertainties": _string_list(tool_input.get("uncertainties"), limit=MAX_TRAVEL_ITEMS),
        "approval_note": _bounded_text(tool_input.get("approval_note")),
        "reason": reason,
        "path": str(markdown_path),
        "booking_status": "prepared_not_booked",
        "approval_required": True,
        "passenger_data_status": "not_transmitted",
        "payment_status": "not_paid",
        "safety_note": (
            "Prepared review artifact only. No booking, ticket, PNR, payment, passenger-data submission, "
            "cancellation, captcha, OTP, or account change was executed."
        ),
    }


def _booking_options(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("Travel booking options must be a list.")
    options = []
    for index, raw in enumerate(value[:MAX_TRAVEL_ITEMS], start=1):
        if not isinstance(raw, dict):
            raise ValueError("Each travel booking option must be an object.")
        label = _bounded_text(raw.get("label") or raw.get("name") or raw.get("carrier_or_train_name"))
        if not label:
            raise ValueError("Each travel booking option requires a label, name, or carrier_or_train_name.")
        option_id = _bounded_text(raw.get("option_id")) or f"option-{index}"
        options.append(
            {
                "option_id": option_id,
                "label": label,
                "provider": _bounded_text(raw.get("provider")),
                "operator": _bounded_text(raw.get("operator") or raw.get("carrier_or_train_name")),
                "number": _bounded_text(raw.get("number") or raw.get("train_number") or raw.get("flight_number")),
                "origin": _bounded_text(raw.get("origin")),
                "destination": _bounded_text(raw.get("destination")),
                "departure": _bounded_text(raw.get("departure") or raw.get("departure_time")),
                "arrival": _bounded_text(raw.get("arrival") or raw.get("arrival_time")),
                "duration": _bounded_text(raw.get("duration")),
                "class_or_cabin": _bounded_text(raw.get("class_or_cabin") or raw.get("journey_class") or raw.get("cabin")),
                "quota_or_fare_family": _bounded_text(raw.get("quota_or_fare_family") or raw.get("quota") or raw.get("fare_family")),
                "fare": _bounded_text(raw.get("fare") or raw.get("price")),
                "availability_status": _bounded_text(raw.get("availability_status") or raw.get("availability")),
                "baggage_or_allowance": _bounded_text(raw.get("baggage_or_allowance") or raw.get("baggage")),
                "change_refund_terms": _bounded_text(raw.get("change_refund_terms") or raw.get("refund_terms")),
                "source_ref": _bounded_text(raw.get("source_ref")),
                "notes": _bounded_text(raw.get("notes")),
            }
        )
    return options


def _booking_checks(value: Any) -> list[dict[str, str]]:
    checks = []
    for raw in _bounded_list(value, MAX_TRAVEL_ITEMS):
        if not isinstance(raw, dict):
            continue
        name = _bounded_text(raw.get("name"))
        if not name:
            continue
        checks.append({"name": name, "status": _bounded_text(raw.get("status") or "unknown"), "evidence": _bounded_text(raw.get("evidence"))})
    return checks


def _render_travel_plan(plan: dict[str, Any]) -> str:
    lines = [f"# {plan['title']}", "", f"Status: {plan['status']}", f"Approval status: {plan['approval_status']}", ""]
    for key in ("origin", "destination", "date_range", "travelers", "budget", "evidence_checked_at"):
        if plan[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {plan[key]}")
    lines.append("")
    _append_list(lines, "Preferences", plan["preferences"])
    _append_list(lines, "Constraints", plan["constraints"])
    if plan["route_options"]:
        lines.extend(["## Route Options", "", "| Label | Mode | Duration | Cost | Reliability | Accessibility | Tradeoffs | Source |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
        for route in plan["route_options"]:
            lines.append(
                f"| {route['label']} | {route['mode']} | {route['estimated_duration']} | {route['estimated_cost']} | {route['reliability']} | {route['accessibility']} | {route['tradeoffs']} | {route['source_ref']} |"
            )
        lines.append("")
    if plan["places"]:
        lines.extend(["## Places", "", "| Name | Kind | Location | Hours | Cost | Notes | Source |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for place in plan["places"]:
            lines.append(f"| {place['name']} | {place['kind']} | {place['location']} | {place['hours']} | {place['cost']} | {place['notes']} | {place['source_ref']} |")
        lines.append("")
    if plan["itinerary_days"]:
        lines.extend(["## Itinerary", ""])
        for day in plan["itinerary_days"]:
            lines.extend([f"### {day['label']}", "", day["summary"], ""])
            for item in day["items"]:
                prefix = f"{item['time']} - " if item["time"] else ""
                location = f" ({item['location']})" if item["location"] else ""
                notes = f": {item['notes']}" if item["notes"] else ""
                lines.append(f"- {prefix}{item['activity']}{location}{notes}")
            lines.append("")
    _append_list(lines, "Source References", plan["source_refs"])
    _append_list(lines, "Uncertainties", plan["uncertainties"])
    _append_list(lines, "Approval Boundaries", plan["approval_boundaries"])
    lines.append(f"Created: {plan['created_at']}")
    return "\n".join(lines) + "\n"


def _render_booking_intent(intent: dict[str, Any]) -> str:
    lines = [
        f"# {intent['title']}",
        "",
        f"Mode: {intent['mode']}",
        f"Booking status: {intent['booking_status']}",
        f"Approval required: {intent['approval_required']}",
        f"Passenger data: {intent['passenger_data_status']}",
        f"Payment status: {intent['payment_status']}",
        f"Evidence checked at: {intent['evidence_checked_at']}",
        "",
    ]
    for key in ("origin", "destination", "departure_date", "return_date", "travelers", "selected_option_id"):
        if intent[key]:
            lines.append(f"{key.replace('_', ' ').title()}: {intent[key]}")
    lines.append("")
    _append_list(lines, "Passenger Requirements", intent["passenger_requirements"])
    _append_list(lines, "Preferences", intent["preferences"])
    lines.extend(
        [
            "## Options",
            "",
            "| ID | Label | Provider | Operator | Number | Origin | Destination | Departure | Arrival | Duration | Class/Cabin | Quota/Fare Family | Fare | Availability | Allowance | Changes/Refunds | Source | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for option in intent["options"]:
        lines.append(
            f"| {option['option_id']} | {option['label']} | {option['provider']} | {option['operator']} | {option['number']} | {option['origin']} | {option['destination']} | {option['departure']} | {option['arrival']} | {option['duration']} | {option['class_or_cabin']} | {option['quota_or_fare_family']} | {option['fare']} | {option['availability_status']} | {option['baggage_or_allowance']} | {option['change_refund_terms']} | {option['source_ref']} | {option['notes']} |"
        )
    lines.append("")
    if intent["checks"]:
        lines.extend(["## Checks", "", "| Check | Status | Evidence |", "| --- | --- | --- |"])
        for check in intent["checks"]:
            lines.append(f"| {check['name']} | {check['status']} | {check['evidence']} |")
        lines.append("")
    _append_list(lines, "Uncertainties", intent["uncertainties"])
    _append_list(lines, "Source References", intent["source_refs"])
    if intent["approval_note"]:
        lines.extend(["## Approval Note", "", intent["approval_note"], ""])
    lines.extend(["## Safety Note", "", intent["safety_note"], "", f"Created: {intent['created_at']}"])
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
