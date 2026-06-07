"""
agent.py
Agentic reasoning layer - calls Claude to generate clarifying questions,
interpret free-text family situations, and produce personalized action plans.
"""

import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-5-20250929"


def extract_profile_from_text(user_text: str) -> dict:
    """
    Use Claude to parse free-text family situation into a structured profile dict.
    """
    system = """You are a compassionate benefits navigator assistant for New Jersey families.
Extract a structured profile from the family's description. Respond ONLY with valid JSON - no markdown, no explanation.

JSON schema:
{
  "household_size": <int, total people in household>,
  "monthly_income": <float, estimated gross monthly household income in USD. If unknown use 0>,
  "has_children": <bool>,
  "children_ages": <list of ints, ages of all children>,
  "pregnant": <bool>,
  "is_documented": <bool, true if they have legal immigration status or are US citizens>,
  "needs_childcare": <bool>,
  "has_dv_concern": <bool, domestic violence concern>,
  "is_working": <bool>,
  "free_text_summary": <string, 1-sentence summary of situation>
}

If information is not mentioned, use reasonable defaults:
- is_documented: true (assume unless mentioned otherwise)
- has_dv_concern: false
- monthly_income: 0 if not mentioned
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    raw = response.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def generate_clarifying_questions(user_text: str, profile: dict) -> list[str]:
    """
    Generate 2-3 targeted clarifying questions based on what's ambiguous.
    """
    system = """You are a benefits navigator for NJ families. Based on the family description and extracted profile,
identify the 2-3 most important missing pieces of information that would help find the right benefits.
Return ONLY a JSON array of question strings - short, plain English, conversational.
Example: ["How many people live in your household?", "Do you currently have any health insurance?"]
No markdown. No explanation. Just the JSON array."""

    prompt = f"""Family description: {user_text}

Extracted profile so far: {json.dumps(profile, indent=2)}

What are the 2-3 most useful follow-up questions?"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def generate_action_plan(profile: dict, eligible_programs: list[dict]) -> str:
    """
    Generate a warm, personalized action plan given the profile and matched programs.
    """
    system = """You are a compassionate, knowledgeable NJ benefits navigator. 
Write a warm, encouraging, and practical action plan for this family. 

Format guidelines:
- Start with a brief empathetic acknowledgment of their situation (1-2 sentences)
- Group recommendations by benefit category using clear headers
- For each program: explain WHY it fits this family specifically (not just what it is)
- End with 1-2 next steps they should do TODAY
- Keep language simple, friendly, and jargon-free
- Total length: 300-450 words
- Do NOT use markdown code blocks or raw JSON"""

    programs_summary = []
    for p in eligible_programs:
        programs_summary.append({
            "name": p["name"],
            "category": p["category"],
            "description": p["description"],
            "how_to_apply": p["how_to_apply"],
            "match_reasons": p.get("match_reasons", []),
        })

    prompt = f"""Family profile: {json.dumps(profile, indent=2)}

Matched benefit programs: {json.dumps(programs_summary, indent=2)}

Write a personalized action plan for this family."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def merge_profile_with_answers(profile: dict, questions: list[str], answers: list[str]) -> dict:
    """
    Use Claude to merge clarifying Q&A into the existing profile.
    """
    system = """You are updating a family benefits profile based on new answers to clarifying questions.
Merge the new information into the existing profile. Return ONLY the updated JSON profile - no markdown, no explanation."""

    qa_pairs = "\n".join([f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)])

    prompt = f"""Existing profile: {json.dumps(profile, indent=2)}

New Q&A:
{qa_pairs}

Return the updated profile JSON."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return profile  # fallback: keep original if parse fails
