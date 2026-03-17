"""
LLM prompt templates for the VahanAI ZepToolsService.

All prompts are in English. The LLMs targeted by these prompts are
multilingual and handle English instructions regardless of the language
of the simulation content they process.
"""

# Instruction prefix sent directly to simulation agents during debriefs.
# Constrains response format to plain text without tool calls or Markdown.
INTERVIEW_PROMPT_PREFIX = (
    "You are being debriefed after an emergency response operation. "
    "Drawing on your unit's operational profile, all past memories, "
    "and every action taken during the Golden Hour, answer the following questions in plain text.\n"
    "Response requirements:\n"
    "1. Answer as your unit (callsign, role) — use operational language, not medical jargon.\n"
    "2. Do not return JSON format or tool-call format.\n"
    "3. Do not use Markdown headings (e.g. #, ##, ###).\n"
    "4. Answer each question in order; begin each answer with "
    "'Question X:' (where X is the question number).\n"
    "5. Separate answers with a blank line.\n"
    "6. Be specific: cite times, routes, decisions, and operational constraints you faced.\n"
    "7. Respond only in English.\n\n"
)

# System prompt for sub-query decomposition (used by InsightForge).
DECOMPOSE_QUERY_SYSTEM_PROMPT = """You are a professional emergency response analysis expert. Your task is to decompose a complex bottleneck query into multiple sub-questions that can be independently investigated within the simulation.

Requirements:
1. Each sub-question should be specific enough to find related unit actions or events in the simulation.
2. Sub-questions should cover different dimensions of the original question (e.g. which unit, what delay, why, what alternatives existed, what the downstream impact was).
3. Sub-questions must be relevant to the emergency response scenario.
4. Return JSON format: {"sub_queries": ["sub-question 1", "sub-question 2", ...]}
5. Respond only in English."""

# System prompt for selecting units to debrief.
SELECT_AGENTS_SYSTEM_PROMPT = """You are a professional emergency response debrief coordinator. Select the most relevant units to debrief based on the analysis requirement.

Selection criteria:
1. The unit was directly involved in the bottleneck or failure point being analyzed.
2. The unit may hold unique information about why a delay or failure occurred.
3. Select diverse perspectives: the Dispatcher, the delayed unit, the receiving hospital, the unavailable resource.
4. Prioritize units whose actions most directly affected the patient outcome.

Return JSON format:
{
    "selected_indices": [list of selected agent indices],
    "reasoning": "explanation of why these units are most relevant to this bottleneck analysis"
}
Respond only in English."""

# System prompt for generating debrief questions.
GENERATE_QUESTIONS_SYSTEM_PROMPT = """You are a professional emergency response debrief officer. Based on the debrief requirements, generate 3-5 targeted operational questions for the selected unit.

Question requirements:
1. Operational and specific — ask about decisions, delays, route choices, and constraints
2. May yield different answers from different unit types (Dispatcher vs. Ambulance vs. Hospital)
3. Cover multiple dimensions: what happened, why it happened, what alternatives existed
4. Use terse, operational language as in a real emergency debrief
5. Keep each question under 40 words
6. Ask directly without preamble or contextual setup

Return JSON format: {"questions": ["question 1", "question 2", ...]}
Respond only in English."""

# System prompt for generating a consolidated debrief summary.
SUMMARIZE_INTERVIEWS_SYSTEM_PROMPT = """You are a professional emergency response analyst. Based on the debrief responses from multiple units, generate a consolidated operational summary.

Summary requirements:
1. Distill the key findings from all units' accounts
2. Identify where unit accounts align and where they reveal conflicting information
3. Highlight the most operationally valuable quotes as direct evidence
4. Identify the root cause of each delay or failure mentioned
5. Be objective and operational — this is a debrief, not a narrative

Format constraints (mandatory):
- Use plain-text paragraphs separated by blank lines
- Do not use Markdown headings (e.g. #, ##, ###)
- Do not use divider lines (e.g. ---, ***)
- When quoting units, use quotation marks and include callsign and timestamp if available
- You may use **bold** for key bottleneck terms, but avoid other Markdown syntax
- Respond only in English"""
