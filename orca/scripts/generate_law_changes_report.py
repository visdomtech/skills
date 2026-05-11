#!/usr/bin/env python3
"""Generate a Gmail-compatible HTML law changes report from Orca MCP data."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "Non-Compete & Restrictive Covenant Changes",
        ["non-compete", "noncompete", "restrictive covenant"],
    ),
    (
        "Minimum Wage & Compensation",
        ["minimum wage", "wage", "compensation", "overtime", "salary"],
    ),
    (
        "Anti-Retaliation & Workplace Rights",
        ["retaliation", "whistleblower", "workplace right"],
    ),
    (
        "OSHA & Workplace Safety",
        ["osha", "safety", "workplace safety"],
    ),
    (
        "Notable Court Decisions",
        ["court", "decision", "ruling", "litigation"],
    ),
    (
        "Federal Regulatory Proposals & Updates",
        ["federal", "regulatory", "proposal"],
    ),
]

BUCKET_CONFIG: dict[str, dict[str, str]] = {
    "immediate": {"color": "#dc2626", "bg": "#fef2f2", "label": "Immediate"},
    "upcoming": {"color": "#ea580c", "bg": "#fff7ed", "label": "Upcoming"},
    "ongoing": {"color": "#16a34a", "bg": "#f0fdf4", "label": "Ongoing"},
    "monitor": {"color": "#3b82f6", "bg": "#eff6ff", "label": "Monitor"},
}

JURISDICTION_DISPLAY: dict[str, str] = {
    "US-AL": "Alabama",
    "US-AK": "Alaska",
    "US-AZ": "Arizona",
    "US-AR": "Arkansas",
    "US-CA": "California",
    "US-CO": "Colorado",
    "US-CT": "Connecticut",
    "US-DE": "Delaware",
    "US-FL": "Florida",
    "US-GA": "Georgia",
    "US-HI": "Hawaii",
    "US-ID": "Idaho",
    "US-IL": "Illinois",
    "US-IN": "Indiana",
    "US-IA": "Iowa",
    "US-KS": "Kansas",
    "US-KY": "Kentucky",
    "US-LA": "Louisiana",
    "US-ME": "Maine",
    "US-MD": "Maryland",
    "US-MA": "Massachusetts",
    "US-MI": "Michigan",
    "US-MN": "Minnesota",
    "US-MS": "Mississippi",
    "US-MO": "Missouri",
    "US-MT": "Montana",
    "US-NE": "Nebraska",
    "US-NV": "Nevada",
    "US-NH": "New Hampshire",
    "US-NJ": "New Jersey",
    "US-NM": "New Mexico",
    "US-NY": "New York",
    "US-NC": "North Carolina",
    "US-ND": "North Dakota",
    "US-OH": "Ohio",
    "US-OK": "Oklahoma",
    "US-OR": "Oregon",
    "US-PA": "Pennsylvania",
    "US-RI": "Rhode Island",
    "US-SC": "South Carolina",
    "US-SD": "South Dakota",
    "US-TN": "Tennessee",
    "US-TX": "Texas",
    "US-UT": "Utah",
    "US-VT": "Vermont",
    "US-VA": "Virginia",
    "US-WA": "Washington",
    "US-WV": "West Virginia",
    "US-WI": "Wisconsin",
    "US-WY": "Wyoming",
    "US-DC": "District of Columbia",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LawChange:
    bill_number: str = ""
    jurisdiction: str = "N/A"
    change_type: str = "Unknown"
    summary: str = "No summary available"
    detailed_description: str = ""
    effective_date: Optional[str] = None
    enactment_date: Optional[str] = None
    revised_effective_date: Optional[str] = None
    revised_enactment_date: Optional[str] = None
    status: str = "Unknown"
    tracker_stem: str = ""
    research_content: str = ""
    upload_date: Optional[str] = None
    notes: str = ""

    # Computed after analysis
    priority: str = "low"
    days_until_effective: Optional[int] = None
    category: str = ""

    @staticmethod
    def compute_days_until(
        effective_date_str: Optional[str], now: datetime
    ) -> Optional[int]:
        """Return days from *now* until *effective_date_str*, or None if unparseable."""
        if not effective_date_str or effective_date_str == "NONE":
            return None
        try:
            if len(effective_date_str) == 10 and effective_date_str.count("-") == 2:
                dt = datetime.fromisoformat(effective_date_str).replace(
                    tzinfo=timezone.utc
                )
            else:
                dt = datetime.fromisoformat(
                    effective_date_str.replace("Z", "+00:00")
                )
            return (dt - now).days
        except (ValueError, TypeError):
            return None

    @property
    def combined_text(self) -> str:
        return " ".join(
            [
                self.tracker_stem,
                self.summary,
                self.research_content,
            ]
        ).lower()


@dataclass
class AnalysisResult:
    total: int = 0
    change_type_counts: dict[str, int] = field(default_factory=dict)
    jurisdiction_counts: dict[str, int] = field(default_factory=dict)
    sorted_jurisdictions: list[tuple[str, int]] = field(default_factory=list)
    earliest_date: Optional[datetime] = None
    latest_date: Optional[datetime] = None
    date_range_display: str = ""
    categorized_changes: OrderedDict[str, list[LawChange]] = field(
        default_factory=OrderedDict
    )
    high_priority: list[LawChange] = field(default_factory=list)
    medium_priority: list[LawChange] = field(default_factory=list)
    low_priority: list[LawChange] = field(default_factory=list)
    all_changes: list[LawChange] = field(default_factory=list)


@dataclass
class ActionItemGroup:
    title: str
    theme_slug: str
    border_color: str
    background_color: str
    narrative: str


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_raw_changes(path: str) -> list[dict]:
    """Load raw law-change dicts from a cache file or raw API JSON file."""
    with open(path) as fh:
        raw = json.load(fh)

    if "response" in raw and "data" in raw["response"]:
        return raw["response"]["data"]["changes"]
    return raw["changes"]


def parse_law_change(raw: dict) -> LawChange:
    """Convert a raw API dict into a LawChange dataclass."""
    return LawChange(
        bill_number=raw.get("billNumber", ""),
        jurisdiction=raw.get("jurisdiction", "N/A"),
        change_type=raw.get("changeType", "Unknown"),
        summary=raw.get("summary", "No summary available"),
        detailed_description=raw.get("detailedDescription", ""),
        effective_date=raw.get("effectiveDate") or None,
        enactment_date=raw.get("enactmentDate") or None,
        revised_effective_date=raw.get("revisedEffectiveDate") or None,
        revised_enactment_date=raw.get("revisedEnactmentDate") or None,
        status=raw.get("status", "Unknown"),
        tracker_stem=raw.get("trackerStem", ""),
        research_content=raw.get("researchContent", ""),
        upload_date=raw.get("uploadDate") or None,
        notes=raw.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string safely, returning None on failure."""
    if not date_str:
        return None
    try:
        if len(date_str) == 10 and date_str.count("-") == 2:
            return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _format_date(date_str: Optional[str]) -> str:
    if not date_str:
        return "N/A"
    try:
        dt = _parse_date_safe(date_str)
        return dt.strftime("%b %d, %Y") if dt else date_str
    except ValueError:
        return date_str


def _jurisdiction_display(code: str) -> str:
    return JURISDICTION_DISPLAY.get(code, code)


def _smart_jurisdiction(lc: LawChange) -> str:
    """Return best-guess display jurisdiction, overriding 'US' for city/county items."""
    if lc.jurisdiction != "US":
        return _jurisdiction_display(lc.jurisdiction)
    # Check if summary mentions a specific city or state
    txt = lc.summary.lower()
    for city, state_code in [
        ("pasadena", "US-CA"),
        ("los angeles", "US-CA"),
        ("san francisco", "US-CA"),
        ("chicago", "US-IL"),
        ("new york city", "US-NY"),
        ("seattle", "US-WA"),
        ("portland", "US-OR"),
        ("austin", "US-TX"),
        ("miami", "US-FL"),
    ]:
        if city in txt:
            return _jurisdiction_display(state_code)
    return "Federal"


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def categorize_change(lc: LawChange) -> str:
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in lc.combined_text:
                return category
    return "Other Law Changes"


def _assign_priority(lc: LawChange, now: datetime) -> tuple[str, int | None]:
    """Return (priority, days_until_effective) for a law change."""
    days = LawChange.compute_days_until(lc.revised_effective_date, now)

    if lc.change_type == "New Law":
        return ("high", days)
    if days is not None:
        if 0 <= days <= 30:
            return ("high", days)
        if 30 < days <= 90:
            return ("medium", days)
        if days < 0:
            return ("low", days)
        return ("medium", days)

    if lc.change_type in ("Amendment", "Update"):
        return ("medium", days)
    return ("low", days)


def analyze(changes: list[LawChange], now: datetime) -> AnalysisResult:
    result = AnalysisResult()
    result.all_changes = changes
    result.total = len(changes)

    jurisdictions: set[str] = set()

    for lc in changes:
        lc.category = categorize_change(lc)
        lc.priority, lc.days_until_effective = _assign_priority(lc, now)

        # Count change types
        ct = lc.change_type
        result.change_type_counts[ct] = result.change_type_counts.get(ct, 0) + 1

        # Track jurisdictions
        juris = lc.jurisdiction
        jurisdictions.add(juris)
        result.jurisdiction_counts[juris] = (
            result.jurisdiction_counts.get(juris, 0) + 1
        )

        # Track date range from enactment dates
        dt = _parse_date_safe(lc.revised_enactment_date)
        if dt:
            if result.earliest_date is None or dt < result.earliest_date:
                result.earliest_date = dt
            if result.latest_date is None or dt > result.latest_date:
                result.latest_date = dt

        # Priority buckets
        if lc.priority == "high":
            result.high_priority.append(lc)
        elif lc.priority == "medium":
            result.medium_priority.append(lc)
        else:
            result.low_priority.append(lc)

        # Categorize
        if lc.category not in result.categorized_changes:
            result.categorized_changes[lc.category] = []
        result.categorized_changes[lc.category].append(lc)

    # Sort jurisdictions by count desc
    result.sorted_jurisdictions = sorted(
        result.jurisdiction_counts.items(), key=lambda x: x[1], reverse=True
    )

    # Sort categories by count desc
    result.categorized_changes = OrderedDict(
        sorted(result.categorized_changes.items(), key=lambda x: len(x[1]), reverse=True)
    )

    # Date range display
    if result.earliest_date and result.latest_date:
        result.date_range_display = (
            f"{result.earliest_date.strftime('%B %d')} – "
            f"{result.latest_date.strftime('%B %d, %Y')}"
        )
    else:
        result.date_range_display = ""

    return result


# ---------------------------------------------------------------------------
# Action-items engine
# ---------------------------------------------------------------------------


def _group_by_jurisdiction(items: list[LawChange]) -> dict[str, list[LawChange]]:
    groups: dict[str, list[LawChange]] = {}
    for item in items:
        groups.setdefault(item.jurisdiction, []).append(item)
    return groups


def _group_by_effective_date(
    items: list[LawChange],
) -> dict[str, list[LawChange]]:
    """Group items whose effective dates fall within 7-day windows."""
    dated = [
        (lc, d)
        for lc in items
        if (d := LawChange.compute_days_until(
            lc.revised_effective_date, datetime.now(timezone.utc)
        )) is not None
    ]
    # Sort by days-until-effective, then cluster into 7-day windows
    if not dated:
        return {"unknown": items}
    dated.sort(key=lambda x: x[1])
    groups: dict[str, list[LawChange]] = {}
    current_key: Optional[str] = None
    current_days: Optional[int] = None
    for lc, days in dated:
        key_date = lc.revised_effective_date or "unknown"
        if current_days is None or abs(days - current_days) > 7:
            current_key = key_date
            current_days = days
        groups.setdefault(current_key, []).append(lc)
    return groups


def _detect_common_theme(items: list[LawChange]) -> str:
    """Return the most common category across items."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1
    return max(counts, key=counts.get)


def _extract_wage_amount(lc: LawChange) -> Optional[str]:
    m = re.search(r"\$(\d+\.?\d*)/?hr", lc.combined_text)
    if m:
        return f"${m.group(1)}/hr"
    m = re.search(r"\$(\d+\.?\d*)", lc.combined_text)
    return f"${m.group(1)}" if m else None


def _extract_comment_deadline(lc: LawChange) -> Optional[str]:
    """Search for a comment deadline like 'comment by June 5, 2026'."""
    m = re.search(
        r"comment\s+(?:deadline\s+)?(?:by\s+)?(\w+ \d{1,2},?\s*\d{4})",
        lc.combined_text,
    )
    if m:
        return m.group(1)
    return None


def _extract_bills(items: list[LawChange]) -> str:
    """Return human-readable bill list, e.g. 'SB 111 and HB 270', deduplicated."""
    seen: set[str] = set()
    bills: list[str] = []
    for c in items:
        b = c.bill_number
        if b and b != "N/A" and b not in seen:
            seen.add(b)
            bills.append(b)
    if not bills:
        return ""
    if len(bills) == 1:
        return bills[0]
    return ", ".join(bills[:-1]) + " and " + bills[-1]


_NOISE_WORDS = frozenset({
    "the", "any", "all", "these", "this", "such", "their", "those",
    "that", "which", "agreements entered", "law", "laws",
    "non-compete", "noncompete", "non-competition",
    "a person", "an individual", "employees", "employers",
})


def _extract_affected_groups(items: list[LawChange]) -> str:
    """Search for affected parties mentioned in law-change summaries."""
    patterns = [
        r"with\s+(.+?)\s+unless\b",
        r"require\s+(.+?)\s+to\s+enter\b",
        r"prohibit(?:ing|s)?\s+(.+?)\s+from\b",
        r"for\s+(.+?)\s+who\b",
        r"targeting\s+(.+?)(?:\.|,|;|$)",
    ]
    candidates: set[str] = set()
    for item in items:
        # Use only the summary (not full research content) to avoid noise
        txt = item.summary
        for pat in patterns:
            for m in re.finditer(pat, txt, re.IGNORECASE):
                g = m.group(1).strip().lower()
                g = re.sub(r"\s+", " ", g)
                if g not in _NOISE_WORDS and 3 <= len(g) <= 50:
                    for prefix in ["the ", "any ", "all "]:
                        if g.startswith(prefix):
                            g = g[len(prefix):]
                    if g and g not in _NOISE_WORDS:
                        candidates.add(g)

    if not candidates:
        return "employees"

    parts = sorted(candidates, key=len)
    parts = parts[:3]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def _oxford_join(items: list[str]) -> str:
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _bill_ref(cluster: list[LawChange]) -> str:
    """Return a concise bill reference like '(US-UT SB 111)' or empty string."""
    bills = _extract_bills(cluster)
    if not bills:
        return ""
    juris = cluster[0].jurisdiction if cluster else ""
    return f" ({juris} {bills})"


def _narrative_immediate(changes: list[LawChange], now: datetime) -> str:
    """Generate narrative for changes effective within 30 days."""
    by_juris = _group_by_jurisdiction(changes)
    parts: list[str] = []

    for juris, items in sorted(by_juris.items()):
        juris_name = _smart_jurisdiction(items[0]) if items else _jurisdiction_display(juris)
        bills_str = _extract_bills(items)
        bill_ref = f" ({juris} {bills_str})" if bills_str else f" ({juris})"
        theme = _detect_common_theme(items)

        if "Non-Compete" in theme:
            affected = _extract_affected_groups(items)
            parts.append(
                f"Review non-compete agreements with {affected}"
                f"{bill_ref}. Remove or void agreements that do not comply."
            )
        elif "Wage" in theme:
            wage = _extract_wage_amount(items[0]) or "new minimum wage"
            parts.append(
                f"Update payroll systems for {juris_name} to comply with "
                f"{wage} minimum wage{bill_ref}."
            )
        elif "Retaliation" in theme or "Workplace Right" in theme:
            parts.append(
                f"Review {juris_name} anti-retaliation and workplace rights policies "
                f"for compliance with {bills_str or 'new requirements'}."
            )
        elif "Safety" in theme:
            parts.append(
                f"Ensure {juris_name} workplace safety programs comply with "
                f"new requirements{bill_ref}."
            )
        else:
            parts.append(
                f"Review {juris_name} policies for compliance with {bills_str or 'new requirements'}."
            )

    return " ".join(parts)


def _narrative_upcoming(changes: list[LawChange]) -> str:
    """Generate narrative for changes effective 31–90 days out."""
    by_juris = _group_by_jurisdiction(changes)
    parts: list[str] = []

    for juris, items in sorted(by_juris.items()):
        juris_name = _smart_jurisdiction(items[0]) if items else _jurisdiction_display(juris)
        # Merge into theme-based clusters within the jurisdiction
        by_date = _group_by_effective_date(items)
        action_items: list[str] = []
        counter = [0]

        for _date_key, cluster in sorted(by_date.items()):
            theme = _detect_common_theme(cluster)
            bills = _extract_bills(cluster)
            bill_ref = f" ({bills})" if bills else ""

            if "Non-Compete" in theme:
                counter[0] += 1
                action_items.append(
                    f"({counter[0]}) Update non-compete policies to comply with "
                    f"{bills or 'new requirements'}"
                )
            elif "Wage" in theme:
                counter[0] += 1
                wages: list[str] = []
                for c in cluster:
                    w = _extract_wage_amount(c)
                    if w and w not in wages:
                        wages.append(w)
                wage_text = _oxford_join(wages) if wages else "new rates"
                detail = f"{wage_text} minimum wage{bill_ref}"
                action_items.append(f"({counter[0]}) Prepare for {detail}")
            elif "Safety" in theme:
                counter[0] += 1
                action_items.append(
                    f"({counter[0]}) Update safety compliance programs{bill_ref}"
                )
            elif "Retaliation" in theme or "Workplace Right" in theme:
                counter[0] += 1
                action_items.append(
                    f"({counter[0]}) Review workplace rights policies for "
                    f"compliance with {bills or 'new requirements'}"
                )
            else:
                counter[0] += 1
                # Use summary as fallback label, cleaned and truncated
                raw = cluster[0].summary
                raw = re.sub(r"^(?:The|A|An)\s+", "", raw.strip())
                if len(raw) > 60:
                    raw = raw[:57].rsplit(" ", 1)[0] + "..."
                label = bills or raw or "new requirements"
                action_items.append(f"({counter[0]}) Review {label}")

        if action_items:
            parts.append(
                f"{juris_name} employers: {'; '.join(action_items)}."
            )

    return " ".join(parts)


def _narrative_ongoing(changes: list[LawChange]) -> str:
    """Generate narrative for already-effective changes needing ongoing compliance."""
    parts: list[str] = []

    by_theme: dict[str, list[LawChange]] = {}
    for c in changes:
        theme = _detect_common_theme([c])
        by_theme.setdefault(theme, []).append(c)

    if "OSHA & Workplace Safety" in by_theme:
        items = by_theme["OSHA & Workplace Safety"]
        for item in items:
            if "heat" in item.combined_text or "NEP" in item.research_content:
                parts.append(
                    "OSHA's new Heat NEP (CPL 03-00-024) is active for 5 years "
                    "targeting 55 high-risk industries. Ensure heat illness prevention "
                    "programs are current and expect increased inspection activity."
                )
                break
        else:
            parts.append(
                "Review and document OSHA workplace safety compliance programs."
            )

    if "Non-Compete & Restrictive Covenant Changes" in by_theme:
        parts.append(
            "Existing non-compete restrictions remain in effect. Audit current "
            "agreements and prepare for potential legislative changes."
        )

    if "Minimum Wage & Compensation" in by_theme:
        parts.append(
            "Verify payroll systems reflect current minimum wage rates across all "
            "applicable jurisdictions."
        )

    if not parts:
        parts.append(
            "Review ongoing compliance obligations in all applicable jurisdictions."
        )

    return " ".join(parts)


def _short_label(lc: LawChange) -> str:
    """Extract a concise, readable label from a law change for use in narratives."""
    summary = lc.summary
    bill = lc.bill_number if lc.bill_number and lc.bill_number != "N/A" else ""
    juris_name = _jurisdiction_display(lc.jurisdiction)

    # Governor signing summaries → use the bill + jurisdiction
    if re.search(r"governor|signed\s+numerous|signed\s+into\s+law|approved\s+SB|approved\s+HB", summary, re.IGNORECASE):
        if bill:
            return f"{juris_name} {bill}"
        # Extract first bill mention
        m = re.search(r"(?:including|signed)\s+([\w\s,]+)(?:,|\.|and|into|$)", summary, re.IGNORECASE)
        if m:
            return f"{juris_name} {m.group(1).strip()[:60]}"
        return f"{juris_name} legislative update"

    # --- Federal agency proposals ---
    m = re.search(
        r"(?:The\s+)?(?:US\s+)?(DOL|OSHA|NLRB|EEOC|FTC|FinCEN|IRS|MSHA|OPM|FCC|SEC|USCIS)\b",
        summary,
    )
    if m:
        agency = m.group(1)
        # Extract the key topic: look for "notice of proposed rulemaking regarding X",
        # "proposed rule ... X", "final rule ... X", or "announced ... X"
        topic = ""
        for pat in [
            r"(?:notice of\s+)?(?:proposed|final|direct final)\s+rule\s*(?:making)?\s*(?:regarding|on|removing|related to)?\s*(.+?)(?:\.|,|;|and|seeking|pending|under the)",
            r"announced\s+(?:that\s+)?(?:it\s+)?(?:had\s+)?(.+?)(?:\.|,|;|and|seeking|pending|under the)",
            r"published\s+a\s+(.+?)(?:\.|,|;|and|seeking|pending)",
            r"is delaying\s+(.+?)(?:\.|,|;|and|seeking|pending)",
        ]:
            tm = re.search(pat, summary, re.IGNORECASE)
            if tm:
                topic = tm.group(1).strip().rstrip(",")
                break

        if topic and len(topic) > 5:
            # Strip leading articles and redundant prefixes
            topic = re.sub(
                r"^(?:a|an|the)\s+", "", topic, flags=re.IGNORECASE
            )
            topic = re.sub(
                r"^(?:proposed|final|direct final)\s+rule\s*(?:making|related to|regarding|on|removing)?\s*",
                "",
                topic,
                flags=re.IGNORECASE,
            )
            topic = re.sub(
                r"^notice of proposed rulemaking\s*(?:regarding|on)?\s*",
                "",
                topic,
                flags=re.IGNORECASE,
            )
            if len(topic) > 50:
                topic = topic[:47].rsplit(" ", 1)[0] + "..."
            label = f"{agency} {topic}" if topic.strip() else f"{agency} regulatory action"
        else:
            label = f"{agency} regulatory action"
        if bill:
            label += f" ({bill})"
        return label

    # --- State items ---
    topic_matches = [
        (r"non.?compete|non.?competition", "non-compete changes"),
        (r"minimum\s+wage", "minimum wage update"),
        (r"retaliat|whistleblower|workplace\s+right", "workplace rights update"),
        (r"safety|OSHA|heat", "workplace safety update"),
    ]
    for pattern, topic in topic_matches:
        if re.search(pattern, summary, re.IGNORECASE):
            label = f"{juris_name} {topic}"
            if bill:
                label += f" ({bill})"
            return label

    # Fallback: first sentence, shortened
    sentence = summary.split(".")[0].strip()
    label = sentence[:60].rstrip(",")
    if len(sentence) > 60:
        label += "..."
    if bill:
        label = f"{label} ({bill})"
    return label


def _narrative_monitor(changes: list[LawChange]) -> str:
    """Generate narrative for proposals and far-future items to monitor."""
    parts: list[str] = []
    proposals: list[str] = []
    far_future: list[str] = []

    for c in changes:
        deadline = _extract_comment_deadline(c)
        label = _short_label(c)
        if deadline:
            proposals.append(f"{label} (comment by {deadline})")
        elif c.days_until_effective and c.days_until_effective > 90:
            # Far-future effective date — mention the date
            date_str = _format_date(c.revised_effective_date)
            far_future.append(
                f"{label} (effective {date_str})"
            )
        else:
            proposals.append(label)

    if proposals:
        track_items = _oxford_join(proposals)
        parts.append(f"Track {track_items}.")

    if far_future:
        watch_items = _oxford_join(far_future)
        parts.append(f"Monitor {watch_items} for future compliance planning.")

    return " ".join(parts)


def _assign_bucket(lc: LawChange, now: datetime) -> str:
    """Assign a law change to an action-item bucket."""
    days = lc.days_until_effective

    if days is not None:
        if 0 <= days <= 30:
            return "immediate"
        if 30 < days <= 90:
            return "upcoming"
        if days < 0:
            return "ongoing"
        return "monitor"

    # No effective date — monitor (proposals, etc.)
    return "monitor"


def build_action_items(
    result: AnalysisResult, now: datetime
) -> list[ActionItemGroup]:
    """Group all law changes into 4 themed action-item cards with narratives."""

    buckets: dict[str, list[LawChange]] = {
        "immediate": [],
        "upcoming": [],
        "ongoing": [],
        "monitor": [],
    }

    for lc in result.all_changes:
        bucket = _assign_bucket(lc, now)
        buckets[bucket].append(lc)

    # Sort each bucket: high priority first, then by days-until-effective
    for bucket in buckets.values():
        bucket.sort(
            key=lambda c: (
                0 if c.priority == "high" else 1 if c.priority == "medium" else 2,
                c.days_until_effective
                if c.days_until_effective is not None
                else 9999,
            )
        )

    groups: list[ActionItemGroup] = []

    # --- Immediate ---
    if buckets["immediate"]:
        # Title: "Immediate (by <date>)"
        nearest_days = min(
            (c.days_until_effective for c in buckets["immediate"] if c.days_until_effective is not None),
            default=None,
        )
        if nearest_days is not None:
            nearest_date = now.replace(tzinfo=None)
            from datetime import timedelta
            nearest_date = (now + timedelta(days=nearest_days)).strftime("%B %d, %Y")
            title = f"Immediate (by {nearest_date})"
        else:
            title = "Immediate Action Required"

        narrative = _narrative_immediate(buckets["immediate"], now)
        cfg = BUCKET_CONFIG["immediate"]
        groups.append(
            ActionItemGroup(
                title=title,
                theme_slug="immediate",
                border_color=cfg["color"],
                background_color=cfg["bg"],
                narrative=narrative,
            )
        )

    # --- Upcoming ---
    if buckets["upcoming"]:
        # Use the most common effective date or month
        dates = [
            c.revised_effective_date
            for c in buckets["upcoming"]
            if c.revised_effective_date
        ]
        if dates:
            # Pick the most frequent date
            from collections import Counter
            most_common_date = Counter(dates).most_common(1)[0][0]
            parsed = _parse_date_safe(most_common_date)
            if parsed:
                title = f"By {parsed.strftime('%B %d, %Y')}"
            else:
                title = "Upcoming Deadlines"
        else:
            title = "Upcoming Deadlines"

        narrative = _narrative_upcoming(buckets["upcoming"])
        cfg = BUCKET_CONFIG["upcoming"]
        groups.append(
            ActionItemGroup(
                title=title,
                theme_slug="upcoming",
                border_color=cfg["color"],
                background_color=cfg["bg"],
                narrative=narrative,
            )
        )

    # --- Ongoing ---
    if buckets["ongoing"]:
        primary_theme = _detect_common_theme(buckets["ongoing"])
        theme_label = _theme_short_label(primary_theme, buckets["ongoing"])
        # Use a more natural title for diverse ongoing items
        if primary_theme == "Other Law Changes":
            title = "Ongoing Compliance"
        else:
            title = f"Ongoing – {theme_label}"
        narrative = _narrative_ongoing(buckets["ongoing"])
        cfg = BUCKET_CONFIG["ongoing"]
        groups.append(
            ActionItemGroup(
                title=title,
                theme_slug="ongoing",
                border_color=cfg["color"],
                background_color=cfg["bg"],
                narrative=narrative,
            )
        )

    # --- Monitor ---
    if buckets["monitor"]:
        primary_theme = _detect_common_theme(buckets["monitor"])
        theme_label = _theme_short_label(primary_theme, buckets["monitor"])
        title = f"Monitor – {theme_label}"
        narrative = _narrative_monitor(buckets["monitor"])
        cfg = BUCKET_CONFIG["monitor"]
        groups.append(
            ActionItemGroup(
                title=title,
                theme_slug="monitor",
                border_color=cfg["color"],
                background_color=cfg["bg"],
                narrative=narrative,
            )
        )

    return groups


def _theme_short_label(category: str, items: list[LawChange]) -> str:
    """Return a short label that best describes a bucket's theme."""
    # Ordered by specificity — more specific keywords checked first
    priority_keywords = [
        "non-compete",
        "heat",
        "minimum wage",
        "whistleblower",
        "retaliation",
        "safety",
        "osha",
        "wage",
        "proposal",
        "federal",
    ]
    label_map = {
        "non-compete": "Non-Compete Changes",
        "minimum wage": "Minimum Wage",
        "heat": "Heat Safety",
        "safety": "Workplace Safety",
        "osha": "OSHA Compliance",
        "wage": "Wage & Compensation",
        "whistleblower": "Whistleblower",
        "retaliation": "Workplace Rights",
        "proposal": "Federal Proposals",
        "federal": "Federal Updates",
    }

    keyword_hits: dict[str, int] = {}
    for item in items:
        for kw in priority_keywords:
            if kw in item.combined_text:
                keyword_hits[kw] = keyword_hits.get(kw, 0) + 1

    if not keyword_hits:
        return _simplify_category(category)

    # Pick the highest-priority keyword with the most hits
    best_kw = None
    best_score = -1
    for kw in priority_keywords:
        hits = keyword_hits.get(kw, 0)
        if hits > best_score:
            best_score = hits
            best_kw = kw

    return label_map.get(best_kw or "", _simplify_category(category))


def _simplify_category(category: str) -> str:
    """Shorten category names for titles."""
    return category.replace(" Changes", "").replace(" & ", " & ")


# ---------------------------------------------------------------------------
# HTML Renderer
# ---------------------------------------------------------------------------


class ReportRenderer:
    """Renders a Gmail-compatible HTML law changes report."""

    FONT = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Roboto, 'Helvetica Neue', Arial, sans-serif"
    )
    BODY_BG = "#f1f5f9"
    HERO_BG = "#1e3a8a"
    HERO_MUTED = "#94a3b8"
    BORDER = "#e2e8f0"
    TEXT_BODY = "#334155"
    TEXT_MUTED = "#64748b"
    TEXT_HEADING = "#1e293b"
    BLUE_LINK = "#1e3a8a"

    def render(
        self,
        result: AnalysisResult,
        groups: list[ActionItemGroup],
        date_range_label: str,
        now_str: str,
    ) -> str:
        sections = [
            self._hero(result, date_range_label, now_str),
            self._summary_cards(result),
            self._jurisdiction_breakdown(result),
            self._divider(),
            self._categorized_tables(result),
            self._action_items(groups),
            self._footer(result, now_str),
        ]
        body = "\n".join(sections)
        return self._wrap(body)

    # -- Hero ---------------------------------------------------------------

    def _hero(
        self, result: AnalysisResult, date_range_label: str, now_str: str
    ) -> str:
        date_display = result.date_range_display or date_range_label or "No data"
        return f"""
          <!-- Hero -->
          <tr>
            <td style="background-color:{self.HERO_BG};padding:32px 40px;border-radius:12px 12px 0 0;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td valign="middle">
                    <div style="font-size:20px;font-weight:700;color:#fff;">Labor &amp; Employment Law Changes</div>
                    <div style="font-size:14px;color:{self.HERO_MUTED};margin-top:4px;">{date_display}</div>
                    <div style="font-size:12px;color:{self.HERO_MUTED};margin-top:8px;">Report generated on {now_str}</div>
                  </td>
                  <td align="right" valign="middle">
                    <span style="background-color:#ea580c;color:#fff;padding:6px 16px;border-radius:20px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;display:inline-block;">{result.total} CHANGES</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""

    # -- Summary cards ------------------------------------------------------

    def _summary_cards(self, result: AnalysisResult) -> str:
        new_count = result.change_type_counts.get("New Law", 0)
        amendment_count = result.change_type_counts.get("Amendment", 0)
        update_count = result.change_type_counts.get("Update", 0)

        return f"""
          <!-- Summary Cards -->
          <tr>
            <td style="padding:24px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  {self._card(amendment_count, "Amendments", "#ea580c", "#fff7ed", "#fed7aa", padding="right")}
                  {self._card(new_count, "New Laws", "#dc2626", "#fef2f2", "#fecaca", padding="both")}
                  {self._card(update_count, "Updates &amp; Reg Changes", "#16a34a", "#f0fdf4", "#bbf7d0", padding="left")}
                </tr>
              </table>
            </td>
          </tr>"""

    @staticmethod
    def _card(
        count: int, label: str, color: str, bg: str, border: str, padding: str
    ) -> str:
        p = (
            "padding-right:10px;"
            if padding == "right"
            else "padding-left:10px;"
            if padding == "left"
            else "padding:0 5px;"
        )
        return f"""
                  <td width="33%" style="{p}">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:{bg};border:1px solid {border};border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:32px;font-weight:800;color:{color};">{count}</div>
                        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:{color};margin-top:4px;">{label}</div>
                      </td></tr>
                    </table>
                  </td>"""

    # -- Jurisdiction breakdown ---------------------------------------------

    def _jurisdiction_breakdown(self, result: AnalysisResult) -> str:
        rows = ""
        items = result.sorted_jurisdictions
        for i in range(0, len(items), 2):
            left_j, left_c = items[i]
            if i + 1 < len(items):
                right_j, right_c = items[i + 1]
                rows += (
                    f"\n              <tr>"
                    f'<td width="50%" style="padding:4px 0;font-size:12px;color:#475569;">'
                    f'{left_j}: <span style="font-weight:700;color:{self.BLUE_LINK};">{left_c}</span></td>'
                    f'<td width="50%" style="padding:4px 0;font-size:12px;color:#475569;">'
                    f'{right_j}: <span style="font-weight:700;color:{self.BLUE_LINK};">{right_c}</span></td>'
                    f"</tr>"
                )
            else:
                rows += (
                    f"\n              <tr>"
                    f'<td width="50%" style="padding:4px 0;font-size:12px;color:#475569;">'
                    f'{left_j}: <span style="font-weight:700;color:{self.BLUE_LINK};">{left_c}</span></td>'
                    f'<td width="50%" style="padding:4px 0;"></td>'
                    f"</tr>"
                )

        return f"""
          <!-- Jurisdiction Breakdown -->
          <tr>
            <td style="padding:0 40px 24px 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;border-left:3px solid #3b82f6;">
                <tr>
                  <td style="padding:16px 20px;">
                    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:{self.TEXT_MUTED};margin-bottom:12px;">Jurisdiction Breakdown</div>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{rows}
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""

    # -- Categorized tables -------------------------------------------------

    def _categorized_tables(self, result: AnalysisResult) -> str:
        tables = ""
        for category, changes in result.categorized_changes.items():
            rows = ""
            for i, lc in enumerate(changes):
                bg = "#ffffff" if i % 2 == 0 else "#fefce8"
                bill = lc.bill_number or "N/A"
                effective = _format_date(lc.revised_effective_date)
                rows += f"""
                  <tr>
                    <td style="padding:10px 16px;border-bottom:1px solid {self.BORDER};background-color:{bg};font-size:12px;color:{self.TEXT_MUTED};width:40px;">{i + 1}</td>
                    <td style="padding:10px 16px;border-bottom:1px solid {self.BORDER};background-color:{bg};font-weight:600;color:{self.BLUE_LINK};font-size:12px;">{lc.jurisdiction}</td>
                    <td style="padding:10px 16px;border-bottom:1px solid {self.BORDER};background-color:{bg};font-family:monospace;font-size:12px;color:#475569;">{bill}</td>
                    <td style="padding:10px 16px;border-bottom:1px solid {self.BORDER};background-color:{bg};font-size:12px;color:#475569;">{effective}</td>
                    <td style="padding:10px 16px;border-bottom:1px solid {self.BORDER};background-color:{bg};font-size:12px;line-height:1.5;color:{self.TEXT_BODY};">{lc.summary}</td>
                  </tr>"""

            tables += f"""
          <!-- {category} -->
          <tr>
            <td style="padding:0 40px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid {self.BORDER};border-radius:8px;overflow:hidden;margin-bottom:24px;">
                <tr>
                  <td style="background-color:#e0e7ff;border-bottom:2px solid #3b82f6;padding:12px 16px;">
                    <div style="font-size:14px;font-weight:700;color:{self.BLUE_LINK};">{category}</div>
                  </td>
                </tr>
                <tr>
                  <td>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">
                      <thead>
                        <tr>
                          <th style="padding:10px 16px;background-color:#f8fafc;border-bottom:2px solid {self.BORDER};text-align:left;font-size:11px;font-weight:700;color:{self.TEXT_MUTED};text-transform:uppercase;letter-spacing:.8px;width:40px;">#</th>
                          <th style="padding:10px 16px;background-color:#f8fafc;border-bottom:2px solid {self.BORDER};text-align:left;font-size:11px;font-weight:700;color:{self.TEXT_MUTED};text-transform:uppercase;letter-spacing:.8px;">Jurisdiction</th>
                          <th style="padding:10px 16px;background-color:#f8fafc;border-bottom:2px solid {self.BORDER};text-align:left;font-size:11px;font-weight:700;color:{self.TEXT_MUTED};text-transform:uppercase;letter-spacing:.8px;">Bill</th>
                          <th style="padding:10px 16px;background-color:#f8fafc;border-bottom:2px solid {self.BORDER};text-align:left;font-size:11px;font-weight:700;color:{self.TEXT_MUTED};text-transform:uppercase;letter-spacing:.8px;">Effective</th>
                          <th style="padding:10px 16px;background-color:#f8fafc;border-bottom:2px solid {self.BORDER};text-align:left;font-size:11px;font-weight:700;color:{self.TEXT_MUTED};text-transform:uppercase;letter-spacing:.8px;">Summary</th>
                        </tr>
                      </thead>
                      <tbody>{rows}
                      </tbody>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""

        return tables

    # -- Action items -------------------------------------------------------

    def _action_items(self, groups: list[ActionItemGroup]) -> str:
        if not groups:
            return ""

        cards = ""
        for g in groups:
            cards += f"""
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-left:4px solid {g.border_color};background-color:{g.background_color};margin-bottom:16px;">
              <tr><td style="padding:16px 20px;">
                <div style="color:{g.border_color};font-weight:700;font-size:14px;margin-bottom:8px;">{g.title}</div>
                <div style="font-size:13px;line-height:1.6;color:{self.TEXT_HEADING};">{g.narrative}</div>
              </td></tr>
            </table>"""

        return f"""
          <!-- Key Action Items -->
          <tr>
            <td style="padding:0 40px 24px 40px;">
              <div style="font-size:18px;font-weight:700;color:{self.TEXT_HEADING};margin-bottom:16px;">Key Action Items for Employers</div>
              {cards}
            </td>
          </tr>"""

    # -- Footer -------------------------------------------------------------

    def _footer(self, result: AnalysisResult, now_str: str) -> str:
        today = now_str.split(" at ")[0]
        return f"""
          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#f8fafc;border-top:1px solid {self.BORDER};">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td valign="top">
                    <div style="font-size:10px;color:{self.TEXT_MUTED};line-height:1.5;">
                      Data sourced from Orca law change trackers as of {today}.<br>
                      This report covers {result.total} changes across {len(result.categorized_changes)} source trackers. All items are Active status.
                    </div>
                  </td>
                  <td align="right" valign="bottom">
                    <div style="font-size:10px;color:#94a3b8;">DoubleFin &middot; {today}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""

    # -- Dividers & wrappers ------------------------------------------------

    @staticmethod
    def _divider() -> str:
        return """
          <tr>
            <td style="padding:0 48px;">
              <div style="border-top:1px solid #e2e8f0;"></div>
            </td>
          </tr>"""

    def _wrap(self, body: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Orca Law Changes Report</title>
</head>
<body style="margin:0;padding:0;background-color:{self.BODY_BG};font-family:{self.FONT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
    <tr>
      <td align="center" style="padding:48px 16px;">
        <table role="presentation" width="700" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;">
{body}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Gmail-compatible HTML law changes report from Orca JSON data."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="cache/orca_cache_law_changes.json",
        help="Path to cache file or raw API response JSON",
    )
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    os.makedirs(output_dir, exist_ok=True)
    parser.add_argument(
        "output",
        nargs="?",
        default=os.path.join(output_dir, "law_changes_report.html"),
        help="Output HTML file path",
    )
    parser.add_argument(
        "label",
        nargs="?",
        default="Recent Law Changes",
        help="Date range label for the report header",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc)

    # Load & parse
    raw = load_raw_changes(args.input)
    changes = [parse_law_change(r) for r in raw]
    print(f"Loaded {len(changes)} law changes")

    # Analyze
    result = analyze(changes, now)
    nc = result.change_type_counts
    print(
        f"Change types - New Law: {nc.get('New Law', 0)}, "
        f"Amendment: {nc.get('Amendment', 0)}, "
        f"Update: {nc.get('Update', 0)}, "
        f"Total: {result.total}"
    )
    print(f"Jurisdictions: {len(result.jurisdiction_counts)}")
    print(
        f"Priority breakdown - "
        f"High: {len(result.high_priority)}, "
        f"Medium: {len(result.medium_priority)}, "
        f"Low: {len(result.low_priority)}"
    )

    # Action items
    action_groups = build_action_items(result, now)
    print(f"Action item groups: {len(action_groups)}")
    for g in action_groups:
        print(f"  - {g.title}")

    # Render
    now_str = now.strftime("%B %d, %Y at %H:%M UTC")
    renderer = ReportRenderer()
    html = renderer.render(result, action_groups, args.label, now_str)

    with open(args.output, "w") as fh:
        fh.write(html)

    print(f"Report written to {args.output} ({result.total} law changes)")
    print("Done.")


if __name__ == "__main__":
    main()
