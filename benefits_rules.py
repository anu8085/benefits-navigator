"""
benefits_rules.py
Simple eligibility screening logic for NJ benefit programs.
This is a rules-based pre-filter - not a legal determination.
"""

import json
from pathlib import Path

# Federal Poverty Level 2024 - monthly gross income thresholds by household size
FPL_MONTHLY = {
    1: 1255,
    2: 1704,
    3: 2152,
    4: 2601,
    5: 3049,
    6: 3498,
    7: 3946,
    8: 4395,
}

CATEGORY_LABELS = {
    "food": "🥦 Food Support",
    "healthcare": "🏥 Healthcare",
    "childcare": "👶 Childcare",
    "cash": "💵 Cash & Basic Support",
    "family": "🏠 Family Resources",
}


def load_programs() -> list[dict]:
    path = Path(__file__).parent / "sample_data" / "programs.json"
    with open(path) as f:
        return json.load(f)["programs"]


def get_fpl_monthly(household_size: int) -> int:
    size = min(max(household_size, 1), 8)
    return FPL_MONTHLY.get(size, FPL_MONTHLY[8] + (household_size - 8) * 448)


def income_pct_fpl(monthly_income: float, household_size: int) -> float:
    base = get_fpl_monthly(household_size)
    if base == 0:
        return 0
    return (monthly_income / base) * 100


def screen_programs(profile: dict, programs: list[dict] | None = None) -> list[dict]:
    """
    Run simple eligibility pre-screening against all programs.
    Returns list of likely-eligible programs with a match_reason.

    profile keys:
        household_size (int)
        monthly_income (float)
        has_children (bool)
        children_ages (list[int])
        pregnant (bool)
        is_documented (bool)  - True = has legal status / US citizen
        needs_childcare (bool)
        has_dv_concern (bool)
        is_working (bool)

    programs:
        Optional list of program dicts to screen against. When omitted, the
        bundled local sample_data/programs.json is used (unchanged behavior).
        Callers may pass a trusted dataset (e.g. from Unity Catalog) instead.
    """
    if programs is None:
        programs = load_programs()
    household_size = profile.get("household_size", 1)
    monthly_income = profile.get("monthly_income", 0)
    pct_fpl = income_pct_fpl(monthly_income, household_size)

    eligible = []

    for prog in programs:
        reasons = []
        limit = prog.get("income_limit_pct_fpL", 999)
        undoc_ok = prog.get("accepts_undocumented", False)

        # Income check
        if pct_fpl > limit:
            continue

        # Documentation check
        if not profile.get("is_documented", True) and not undoc_ok:
            continue

        # Category-specific checks
        cat = prog["category"]

        if cat == "food":
            if prog["id"] == "snap":
                reasons.append(f"Income (~{pct_fpl:.0f}% FPL) likely within SNAP range")
            if prog["id"] == "wic":
                ages = profile.get("children_ages", [])
                under5 = any(a < 5 for a in ages)
                if profile.get("pregnant") or under5:
                    reasons.append("Pregnancy or child under 5 qualifies for WIC")
                else:
                    continue

        elif cat == "healthcare":
            if prog["id"] == "nj_familycare":
                reasons.append("NJ FamilyCare covers most low-income families")
            if prog["id"] == "chip":
                ages = profile.get("children_ages", [])
                if not any(a < 19 for a in ages):
                    continue
                reasons.append("Child under 19 may qualify for CHIP")

        elif cat == "childcare":
            if prog["id"] == "ccdf":
                if not profile.get("needs_childcare") or not profile.get("is_working"):
                    continue
                ages = profile.get("children_ages", [])
                if not any(a < 13 for a in ages):
                    continue
                reasons.append("Working parent with child under 13 may qualify for subsidy")
            if prog["id"] == "preschool":
                ages = profile.get("children_ages", [])
                if not any(a in [3, 4] for a in ages):
                    continue
                reasons.append("Child age 3-4 may qualify for free NJ preschool")

        elif cat == "cash":
            if prog["id"] == "tanf":
                if not profile.get("has_children"):
                    continue
                reasons.append("Family with children may qualify for TANF cash assistance")
            if prog["id"] == "ga":
                if profile.get("has_children"):
                    continue  # GA is for adults without children
                reasons.append("Single adult may qualify for General Assistance")
            if prog["id"] == "liheap":
                reasons.append("Low-income household may qualify for energy assistance")

        elif cat == "family":
            if prog["id"] == "211nj":
                reasons.append("211 connects all NJ families to local resources")
            if prog["id"] == "ece_home_visit":
                if not profile.get("pregnant") and not any(
                    a <= 2 for a in profile.get("children_ages", [])
                ):
                    continue
                reasons.append("First-time mothers with newborns may get free home visits")
            if prog["id"] == "dv_services":
                if not profile.get("has_dv_concern"):
                    continue
                reasons.append("Domestic violence services available regardless of income")

        prog_copy = dict(prog)
        prog_copy["match_reasons"] = reasons if reasons else ["May be eligible based on income"]
        eligible.append(prog_copy)

    return eligible


def group_by_category(programs: list[dict]) -> dict:
    grouped = {}
    for prog in programs:
        cat = prog["category"]
        grouped.setdefault(cat, []).append(prog)
    return grouped
