# 🧭 Benefits Navigator for Families - NJ MVP

> **Databricks AI Summit Hackathon Project**  
> A conversational AI tool that helps New Jersey families discover and navigate public benefit programs - fast, compassionately, and without bureaucratic jargon.

---

## 🎯 What It Does

1. **User describes their family situation** in plain language (free-text)
2. **AI extracts key profile attributes** (household size, income, children's ages, work status, etc.)
3. **Targeted clarifying questions** are generated to fill in gaps
4. **Rules-based eligibility screening** filters programs across 5 categories
5. **Personalized action plan** is generated - warm, specific, and actionable

---

## 📂 Project Structure

```
benefits_navigator/
├── app.py                  # Streamlit UI (3-step flow)
├── agent.py                # Claude-powered agentic reasoning
├── benefits_rules.py       # Eligibility screening logic + FPL calculator
├── sample_data/
│   └── programs.json       # NJ benefit programs database
└── README.md
```

---

## 🚀 How to Run

### 1. Install dependencies

```bash
pip install streamlit anthropic
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or on Windows:
```cmd
set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Launch the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## 🏗️ Architecture

```
User Input (free text)
        ↓
   agent.py: extract_profile_from_text()     ← Claude (structured JSON extraction)
        ↓
   agent.py: generate_clarifying_questions() ← Claude (targeted follow-up Qs)
        ↓
   User Answers Clarifying Questions
        ↓
   agent.py: merge_profile_with_answers()    ← Claude (profile update)
        ↓
   benefits_rules.py: screen_programs()      ← Rule-based FPL eligibility filter
        ↓
   agent.py: generate_action_plan()          ← Claude (personalized narrative plan)
        ↓
   app.py: Display Results + Program Cards
```

---

## 🗂️ Benefit Categories Covered

| Category | Programs |
|---|---|
| 🥦 Food Support | SNAP, WIC |
| 🏥 Healthcare | NJ FamilyCare (Medicaid), CHIP |
| 👶 Childcare | CCDF Child Care Subsidy, NJ Preschool (PEA) |
| 💵 Cash & Basic Support | TANF / WorkFirst, General Assistance, LIHEAP |
| 🏠 Family Resources | NJ 2-1-1 Helpline, Home Visiting, DV Services |

---

## 🔧 Extending the MVP

| What | How |
|---|---|
| Add more programs | Edit `sample_data/programs.json` |
| Refine eligibility logic | Update `benefits_rules.py` `screen_programs()` |
| Add counties / languages | Extend profile schema and agent prompts |
| Connect to real data | Replace `programs.json` with live API calls (e.g., Benefits.gov API) |
| Add Databricks backend | Log anonymized sessions to Delta Lake for analytics |
| Multilingual support | Add language selector, pass `language` param to agent prompts |

---

## ⚠️ Disclaimer

This tool provides **general information only** and does not constitute legal, financial, or benefits advice. Eligibility is always determined by the relevant agency. Users should verify directly with program administrators.

---

## 👩‍💻 Built For

Databricks AI Summit Hackathon - *Benefits Navigator for Families*  
New Jersey MVP · Powered by Claude (Anthropic) + Streamlit
