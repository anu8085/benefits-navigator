-- ============================================================================
-- social_impact_analytics.sql
--
-- Analytics queries for the Benefits Navigator app-state stored in Lakebase
-- (Postgres). These read the transactional tables the live app writes to:
--
--   family_intake_events(intake_id, event_ts, raw_user_text, profile JSONB)
--   program_matches(match_id, intake_id, event_ts, program_id, program_name,
--                   category, match_reasons JSONB)
--   action_plans(plan_id, intake_id, event_ts, action_plan_text,
--                generated_by_model)
--   user_feedback(feedback_id, intake_id, event_ts, rating, feedback_text)
--
-- Together these queries tell the "social impact" story: how many families we
-- reached, what support they were connected to, and how helpful it was.
-- All queries are read-only.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. Count of family intake events
--
-- What it shows: the total number of families who described their situation
-- and started the navigator.
-- Why it matters: this is our top-of-funnel reach metric - how many households
-- the program actually engaged. It is the denominator for every other rate.
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS total_intake_events
FROM family_intake_events;


-- ----------------------------------------------------------------------------
-- 2. Count of program matches
--
-- What it shows: the total number of program matches surfaced across all
-- families (one family typically matches several programs).
-- Why it matters: measures the breadth of benefit connections we created -
-- every match is a potential door opened to food, healthcare, childcare, or
-- cash support a family may not have known they qualified for.
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS total_program_matches
FROM program_matches;


-- ----------------------------------------------------------------------------
-- 3. Count of generated action plans
--
-- What it shows: how many personalized, step-by-step action plans were
-- generated and delivered to families.
-- Why it matters: an action plan is the concrete, take-away deliverable that
-- turns eligibility into action. Comparing this to intake events (query 1)
-- shows how reliably we convert a conversation into actionable guidance.
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS total_action_plans
FROM action_plans;


-- ----------------------------------------------------------------------------
-- 4. Count of feedback entries
--
-- What it shows: how many families left feedback after receiving their plan.
-- Why it matters: feedback volume is our signal of engagement and the basis
-- for trusting the average rating (query 7). Low feedback counts mean ratings
-- should be read with caution.
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS total_feedback_entries
FROM user_feedback;


-- ----------------------------------------------------------------------------
-- 5. Most common matched program categories
--
-- What it shows: which categories of need (food, healthcare, childcare, cash,
-- family) families match into most often, ranked by volume.
-- Why it matters: reveals where the greatest community need is concentrated,
-- helping prioritize outreach, partnerships, and where to deepen program
-- coverage for the highest social impact.
-- ----------------------------------------------------------------------------
SELECT
    category,
    COUNT(*) AS match_count,
    COUNT(DISTINCT intake_id) AS families_reached
FROM program_matches
GROUP BY category
ORDER BY match_count DESC;


-- ----------------------------------------------------------------------------
-- 6. Most recommended programs
--
-- What it shows: the individual benefit programs that were matched/recommended
-- to families most frequently.
-- Why it matters: identifies the programs doing the heaviest lifting for the
-- community. These are prime candidates for application-assistance partnerships
-- and for verifying that enrollment pipelines can handle the demand we drive.
-- ----------------------------------------------------------------------------
SELECT
    program_id,
    program_name,
    COUNT(*) AS times_recommended,
    COUNT(DISTINCT intake_id) AS families_recommended_to
FROM program_matches
GROUP BY program_id, program_name
ORDER BY times_recommended DESC;


-- ----------------------------------------------------------------------------
-- 7. Average user feedback rating
--
-- What it shows: the mean satisfaction rating (1-5) families gave their plans,
-- alongside the number of ratings it is based on.
-- Why it matters: a direct measure of whether families found the guidance
-- genuinely helpful. Quality of help - not just quantity - is what drives real
-- social impact, and this is our headline trust metric.
-- ----------------------------------------------------------------------------
SELECT
    ROUND(AVG(rating), 2) AS average_rating,
    COUNT(*) AS ratings_count,
    MIN(rating) AS min_rating,
    MAX(rating) AS max_rating
FROM user_feedback
WHERE rating IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 8. Recent user journeys with raw input and action plan
--
-- What it shows: the most recent end-to-end journeys - what a family said in
-- their own words, the plan we generated, how many programs they matched, and
-- their feedback - stitched together by intake_id.
-- Why it matters: behind every metric is a person. These qualitative stories
-- let stakeholders see real impact, surface gaps in matching, and pull
-- testimonials that make the aggregate numbers tangible.
-- ----------------------------------------------------------------------------
SELECT
    fie.intake_id,
    fie.event_ts AS intake_time,
    fie.raw_user_text,
    ap.action_plan_text,
    ap.generated_by_model,
    COUNT(pm.match_id) AS programs_matched,
    uf.rating AS feedback_rating,
    uf.feedback_text
FROM family_intake_events AS fie
LEFT JOIN action_plans  AS ap ON ap.intake_id = fie.intake_id
LEFT JOIN program_matches AS pm ON pm.intake_id = fie.intake_id
LEFT JOIN user_feedback AS uf ON uf.intake_id = fie.intake_id
GROUP BY
    fie.intake_id,
    fie.event_ts,
    fie.raw_user_text,
    ap.action_plan_text,
    ap.generated_by_model,
    uf.rating,
    uf.feedback_text
ORDER BY fie.event_ts DESC
LIMIT 25;
