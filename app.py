"""
app.py
Benefits Navigator for Families - NJ MVP
Streamlit UI with agentic reasoning flow
"""

import logging
import os

import streamlit as st
from agent import (
    extract_profile_from_text,
    generate_clarifying_questions,
    merge_profile_with_answers,
    generate_action_plan,
    MODEL,
)
from benefits_rules import (
    screen_programs,
    group_by_category,
    load_programs,
    CATEGORY_LABELS,
)
from databricks_client import get_benefit_programs_from_databricks

# Lakebase is the TRANSACTIONAL app-state layer: it stores the live records the
# app generates as people use it (intake events, program matches, action plans,
# and feedback). All four writers fail gracefully (return None/False) and never
# raise, so write-back can never crash the app or block the user experience.
from lakebase_client import (
    write_family_intake_event,
    write_program_matches,
    write_action_plan,
    write_user_feedback,
)

# Local SQLite fallback: used ONLY when a Lakebase write fails (e.g. local
# laptop testing or a deleted Lakebase project). Lakebase stays the primary
# store. Standard-library sqlite3 only - no new dependency, no secrets stored.
import local_state_client as local_state

logger = logging.getLogger(__name__)


# ── Trusted benefits data loading ─────────────────────────────────────────────
# Benefit programs are loaded from the TRUSTED source first: the Unity Catalog
# table benefits_navigator.trusted.benefit_programs (via Databricks). If that
# source returns no rows or fails for any reason, we transparently fall back to
# the bundled local sample_data/programs.json so the app always keeps working.
def _adapt_databricks_programs(rows: list[dict]) -> list[dict]:
    """Map trusted Unity Catalog rows to the schema the rules engine expects.

    The Databricks table uses columns like program_id / program_name / apply_url,
    while the rules engine and UI expect id / name / how_to_apply. This adapter
    bridges the two without changing either side.

    The trusted table also carries explicit rule columns (rule_key,
    income_limit_pct_fpl, accepts_undocumented, min_child_age, max_child_age,
    requires_work_or_school). These are mapped onto the exact keys the rules
    engine reads so screening behaves the same as it does for local data:
      * rule_key            -> "id"  (drives the category-specific rule logic)
      * income_limit_pct_fpl -> "income_limit_pct_fpL"
      * accepts_undocumented -> "accepts_undocumented"
    The child-age and work/school fields are passed through under their own keys.
    """
    adapted = []
    for r in rows:
        apply_bits = []
        if r.get("apply_url"):
            apply_bits.append(f"Apply online at {r['apply_url']}")
        if r.get("apply_phone"):
            apply_bits.append(f"call {r['apply_phone']}")
        how_to_apply = (
            " or ".join(apply_bits)
            if apply_bits
            else (r.get("eligibility_summary") or "Contact the program for details.")
        )

        # The rules engine switches on "id" using semantic keys (snap, wic, ...);
        # that semantic key lives in rule_key. Fall back to program_id if a row
        # has no rule_key so the program is still surfaced (with a generic reason).
        rule_key = r.get("rule_key") or r.get("program_id")

        # Use the table's real income cap; default to 999 (no cap) only when the
        # value is missing, mirroring the rules engine's own default.
        income_limit = r.get("income_limit_pct_fpl")
        if income_limit is None:
            income_limit = 999

        adapted.append(
            {
                "id": rule_key,
                "name": r.get("program_name"),
                "category": r.get("category"),
                "description": r.get("description") or "",
                "eligibility_notes": r.get("eligibility_summary") or "",
                "how_to_apply": how_to_apply,
                "url": r.get("apply_url") or r.get("source_url") or "",
                # Rule columns mapped to the exact keys benefits_rules.py expects.
                "income_limit_pct_fpL": income_limit,
                "accepts_undocumented": bool(r.get("accepts_undocumented")),
                # Additional rule fields passed through for completeness.
                "min_child_age": r.get("min_child_age"),
                "max_child_age": r.get("max_child_age"),
                "requires_work_or_school": r.get("requires_work_or_school"),
                # Keep the surrogate program_id for provenance/correlation.
                "program_id": r.get("program_id"),
                # Preserve source labeling / provenance for transparency.
                "source_name": r.get("source_name"),
                "source_url": r.get("source_url"),
                "source_type": r.get("source_type"),
            }
        )
    return adapted


@st.cache_data(show_spinner=False)
def load_benefit_programs() -> tuple[list[dict], str]:
    """Return (programs, source) using Databricks first, then local fallback.

    source is "databricks" when trusted Unity Catalog data is used, or "local"
    when the bundled JSON fallback is used. Cached so the warehouse is not
    queried on every Streamlit rerun.
    """
    rows = get_benefit_programs_from_databricks()
    if rows:
        return _adapt_databricks_programs(rows), "databricks"
    return load_programs(), "local"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Benefits Navigator NJ",
    page_icon="🧭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&family=Inter:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3 {
        font-family: 'Nunito', sans-serif !important;
        font-weight: 800 !important;
    }

    .hero-title {
        font-family: 'Nunito', sans-serif;
        font-size: 2.4rem;
        font-weight: 800;
        color: #1a3a5c;
        line-height: 1.2;
        margin-bottom: 0.25rem;
    }

    .hero-sub {
        font-size: 1.05rem;
        color: #4a6a8a;
        margin-bottom: 1.5rem;
    }

    .badge {
        display: inline-block;
        background: #e8f4fd;
        color: #1a3a5c;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        margin-bottom: 1rem;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    .program-card {
        background: #ffffff;
        border: 1px solid #dce8f5;
        border-left: 5px solid #2e86de;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .program-name {
        font-family: 'Nunito', sans-serif;
        font-weight: 700;
        font-size: 1rem;
        color: #1a3a5c;
        margin-bottom: 0.2rem;
    }

    .program-desc {
        font-size: 0.88rem;
        color: #4a6a8a;
        margin-bottom: 0.4rem;
    }

    .reason-tag {
        display: inline-block;
        background: #eaf7ec;
        color: #256a35;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 4px;
        margin-bottom: 4px;
    }

    .apply-link {
        font-size: 0.82rem;
        color: #2e86de;
        font-weight: 600;
    }

    .action-plan-box {
        background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
        border: 1px solid #c0d9f0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
        font-size: 0.95rem;
        line-height: 1.7;
        color: #1a3a5c;
    }

    .step-indicator {
        background: #2e86de;
        color: white;
        font-family: 'Nunito', sans-serif;
        font-weight: 700;
        font-size: 0.8rem;
        padding: 4px 14px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 0.75rem;
    }

    .stTextArea textarea {
        font-size: 0.95rem !important;
        border-radius: 10px !important;
        border-color: #c0d9f0 !important;
    }

    .stTextInput input {
        border-radius: 8px !important;
        border-color: #c0d9f0 !important;
    }

    .stButton > button {
        background: #2e86de !important;
        color: white !important;
        font-family: 'Nunito', sans-serif !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.5rem 1.5rem !important;
        font-size: 0.95rem !important;
    }

    .stButton > button:hover {
        background: #1a5fa8 !important;
    }

    hr {
        border-color: #dce8f5;
        margin: 1.5rem 0;
    }

    .disclaimer {
        font-size: 0.78rem;
        color: #8aa0b8;
        margin-top: 2rem;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="badge">🗽 New Jersey · Free · Confidential</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">🧭 Benefits Navigator<br>for Families</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Tell us about your family - we\'ll find the right support programs and build your action plan.</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Load benefits data (trusted Databricks first, local JSON fallback) ─────────
programs_data, data_source = load_benefit_programs()
if data_source == "databricks":
    st.caption("🔒 Using trusted Databricks benefits data")
else:
    st.caption("📁 Using local fallback benefits data")

# ── Session state init ─────────────────────────────────────────────────────────
for key in [
    "stage",
    "profile",
    "questions",
    "eligible_programs",
    "action_plan",
    "raw_user_text",
    "intake_id",
    "lakebase_save_ok",
    "state_storage_mode",
    "feedback_saved_where",
    "feedback_submitted",
]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.stage is None:
    st.session_state.stage = "intake"

# ════════════════════════════════════════════════════════
# STAGE 1 - INTAKE
# ════════════════════════════════════════════════════════
if st.session_state.stage == "intake":
    st.markdown('<div class="step-indicator">Step 1 of 3 - Tell us about your family</div>', unsafe_allow_html=True)

    user_text = st.text_area(
        "Describe your family situation in your own words:",
        placeholder=(
            "For example: I'm a single mom with two kids ages 3 and 7. "
            "I work part-time and make about $1,800 a month. "
            "We don't have health insurance right now and I need childcare help."
        ),
        height=140,
        key="intake_text",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        go = st.button("Find Benefits →")

    if go:
        if not user_text.strip():
            st.warning("Please describe your situation first.")
        else:
            with st.spinner("Understanding your situation..."):
                profile = extract_profile_from_text(user_text)
                questions = generate_clarifying_questions(user_text, profile)
                st.session_state.profile = profile
                st.session_state.questions = questions
                # Keep the original free-text so it can be persisted to Lakebase
                # later, after the action plan is generated.
                st.session_state.raw_user_text = user_text
                st.session_state.stage = "clarify"
                st.rerun()

# ════════════════════════════════════════════════════════
# STAGE 2 - CLARIFYING QUESTIONS
# ════════════════════════════════════════════════════════
elif st.session_state.stage == "clarify":
    st.markdown('<div class="step-indicator">Step 2 of 3 - A few quick questions</div>', unsafe_allow_html=True)
    st.markdown("Just a couple more details to make your plan as accurate as possible.")

    answers = []
    questions = st.session_state.questions or []

    for i, q in enumerate(questions):
        ans = st.text_input(q, key=f"clarify_{i}")
        answers.append(ans)

    st.markdown("")
    col1, col2 = st.columns([1, 3])
    with col1:
        next_btn = st.button("Build My Plan →")
    with col2:
        skip_btn = st.button("Skip - use what you have")

    if next_btn or skip_btn:
        with st.spinner("Screening programs and building your plan..."):
            if next_btn and any(a.strip() for a in answers):
                updated_profile = merge_profile_with_answers(
                    st.session_state.profile, questions, answers
                )
            else:
                updated_profile = st.session_state.profile

            st.session_state.profile = updated_profile
            eligible = screen_programs(updated_profile, programs_data)
            st.session_state.eligible_programs = eligible

            if eligible:
                plan = generate_action_plan(updated_profile, eligible)
            else:
                plan = (
                    "Based on the information provided, we weren't able to match specific programs "
                    "right now - but don't give up! Call **NJ 2-1-1** (dial 2-1-1 or text your zip "
                    "to 898-211) anytime for free, expert help finding local resources."
                )

            st.session_state.action_plan = plan

            # ── App-state write-back: Lakebase first, SQLite fallback ──────────
            # Lakebase stays the PRIMARY transactional store (unchanged). Only if
            # a Lakebase write fails do we persist the SAME state into a local
            # SQLite database so a demo journey is never lost. The plan is never
            # blocked on persistence; all writers degrade quietly.
            intake_id = None
            storage_mode = "none"
            try:
                intake_id = write_family_intake_event(
                    updated_profile, st.session_state.raw_user_text or ""
                )
                if intake_id:
                    matches_ok = write_program_matches(intake_id, eligible)
                    plan_id = write_action_plan(intake_id, plan, MODEL)
                    if matches_ok and plan_id:
                        storage_mode = "lakebase"
            except Exception:
                # Never surface internals (or secrets) to the UI; degrade quietly.
                intake_id = None

            if storage_mode != "lakebase":
                # Lakebase unavailable or partial failure -> local SQLite fallback.
                logger.warning(
                    "Lakebase app-state write unavailable; using local SQLite "
                    "fallback."
                )
                try:
                    local_intake_id = local_state.write_family_intake_event(
                        updated_profile, st.session_state.raw_user_text or ""
                    )
                    if local_intake_id:
                        local_state.write_program_matches(local_intake_id, eligible)
                        local_state.write_action_plan(local_intake_id, plan, MODEL)
                        intake_id = local_intake_id
                        storage_mode = "sqlite_fallback"
                        logger.info("App-state saved via local SQLite fallback.")
                    else:
                        storage_mode = "none"
                except Exception:
                    storage_mode = "none"

                if storage_mode == "none":
                    logger.error(
                        "App-state saving failed in BOTH Lakebase and local "
                        "SQLite fallback."
                    )

            # Store intake_id (Lakebase or SQLite) so feedback reuses the same id.
            st.session_state.intake_id = intake_id
            st.session_state.state_storage_mode = storage_mode
            # Backward-compatible flag retained for any existing references.
            st.session_state.lakebase_save_ok = (storage_mode == "lakebase")

            st.session_state.stage = "results"
            st.rerun()

# ════════════════════════════════════════════════════════
# STAGE 3 - RESULTS
# ════════════════════════════════════════════════════════
elif st.session_state.stage == "results":
    st.markdown('<div class="step-indicator">Step 3 of 3 - Your Personalized Action Plan</div>', unsafe_allow_html=True)

    # Action Plan
    st.markdown("### 📋 Your Action Plan")
    st.markdown(
        f'<div class="action-plan-box">{st.session_state.action_plan}</div>',
        unsafe_allow_html=True,
    )

    # Tell the user where the app state was saved, without implying their plan is
    # invalid - the plan above is always fully usable.
    _mode = st.session_state.state_storage_mode
    if _mode == "lakebase":
        st.success("Plan saved to Lakebase app-state tables.")
    elif _mode == "sqlite_fallback":
        st.info(
            "Plan generated successfully. Lakebase is unavailable, so this "
            "session was saved locally in SQLite for demo fallback."
        )
    elif _mode == "none":
        st.warning("Plan generated successfully, but app-state saving failed.")

    st.markdown("---")

    # Matched Programs
    eligible = st.session_state.eligible_programs or []
    if eligible:
        st.markdown(f"### 🎯 Programs You May Qualify For ({len(eligible)} found)")
        grouped = group_by_category(eligible)

        for cat, label in CATEGORY_LABELS.items():
            progs = grouped.get(cat, [])
            if not progs:
                continue
            st.markdown(f"#### {label}")
            for p in progs:
                reasons_html = "".join(
                    f'<span class="reason-tag">✓ {r}</span>'
                    for r in p.get("match_reasons", [])
                )
                st.markdown(
                    f"""
                    <div class="program-card">
                        <div class="program-name">{p['name']}</div>
                        <div class="program-desc">{p['description']}</div>
                        {reasons_html}
                        <br/><br/>
                        <span class="apply-link">📌 How to apply: {p['how_to_apply']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No programs matched. Try calling NJ 2-1-1 for personalized help.")

    st.markdown("---")

    # ── Feedback ──────────────────────────────────────────────────────────────
    # Lets the user rate the plan; the rating + optional comment are written to
    # Lakebase against the same intake_id captured above.
    st.markdown("### 💬 Was this helpful?")
    if st.session_state.feedback_submitted:
        if st.session_state.feedback_saved_where == "sqlite_fallback":
            st.success(
                "Thanks for your feedback! Saved locally in SQLite for demo "
                "fallback."
            )
        else:
            st.success("Thanks for your feedback! Saved to Lakebase.")
    else:
        rating = st.slider(
            "Rate your plan (1 = not helpful, 5 = very helpful)",
            min_value=1,
            max_value=5,
            value=5,
            key="fb_rating",
        )
        comment = st.text_area(
            "Any comments? (optional)",
            key="fb_comment",
        )
        if st.button("Submit Feedback"):
            feedback_id = None
            saved_where = None
            _mode = st.session_state.state_storage_mode

            # If the session was saved to Lakebase, try Lakebase feedback first,
            # then fall back to SQLite. If the session was already a SQLite
            # fallback, write feedback to SQLite directly. Otherwise try both.
            if _mode != "sqlite_fallback":
                try:
                    feedback_id = write_user_feedback(
                        st.session_state.intake_id, rating, comment
                    )
                except Exception:
                    feedback_id = None
                if feedback_id:
                    saved_where = "lakebase"

            if not feedback_id:
                try:
                    feedback_id = local_state.write_user_feedback(
                        st.session_state.intake_id, rating, comment
                    )
                except Exception:
                    feedback_id = None
                if feedback_id:
                    saved_where = "sqlite_fallback"
                    logger.info("Feedback saved via local SQLite fallback.")

            if feedback_id:
                st.session_state.feedback_saved_where = saved_where
                st.session_state.feedback_submitted = True
                st.rerun()
            else:
                logger.error("Feedback save failed in both Lakebase and SQLite.")
                st.warning("Feedback could not be saved right now.")

    st.markdown("---")

    # Start over
    if st.button("🔄 Start Over"):
        for key in [
            "stage",
            "profile",
            "questions",
            "eligible_programs",
            "action_plan",
            "raw_user_text",
            "intake_id",
            "lakebase_save_ok",
            "state_storage_mode",
            "feedback_saved_where",
            "feedback_submitted",
        ]:
            st.session_state[key] = None
        # Clear widget-backed keys so a fresh session starts clean.
        for wkey in ["intake_text", "fb_rating", "fb_comment"]:
            st.session_state.pop(wkey, None)
        st.rerun()

    # Optional debug view of the local SQLite fallback (off by default so the
    # deployed app stays clean). Enable with SHOW_LOCAL_STATE_DEBUG=true.
    if os.environ.get("SHOW_LOCAL_STATE_DEBUG", "").lower() == "true":
        with st.expander("Local SQLite fallback state counts"):
            st.write("Database path:", local_state.get_db_path())
            st.write(local_state.get_local_state_counts())

    st.markdown(
        '<div class="disclaimer">⚠️ This tool provides general information only and does not constitute legal or financial advice. '
        "Eligibility is determined by the relevant agency. Always verify directly with program administrators.</div>",
        unsafe_allow_html=True,
    )
