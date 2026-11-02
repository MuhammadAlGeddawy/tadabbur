"""Prompts for the two LLM steps. Both ask for JSON only; neither may write Quranic text."""

LANGUAGES = ("msa", "egyptian", "gulf", "levantine", "maghrebi", "franco", "english", "other")
INTENTS = ("concept", "verse_lookup", "ruling", "out_of_scope")


def understand_prompt(query: str) -> str:
    return f"""You are the query-understanding step of Tadabbur, a tool that finds Quranic ayat discussing a meaning or concept.
The user's query may be in Modern Standard Arabic, an Arabic dialect (Egyptian, Gulf, Levantine, Maghrebi), Franco-Arabic (Arabic in Latin letters and digits), English, or another language.

Reply with only one JSON object, no other text:
{{"language": "msa" | "egyptian" | "gulf" | "levantine" | "maghrebi" | "franco" | "english" | "other",
 "intent": "concept" | "verse_lookup" | "ruling" | "out_of_scope",
 "msa": "the query restated as a short Modern Standard Arabic description of the concept",
 "classical": ["a paraphrase using Classical / Quranic Arabic vocabulary", "a second, different paraphrase"],
 "english": "a short English gloss"}}

Rules:
- Keep the user's meaning exactly. Do not add new topics.
- Each paraphrase is at most 15 words and names the concept the way classical tafsir would.
- Never write or quote Quranic verse text.
- "ruling" means the user asks for a legal ruling or fatwa. "out_of_scope" means it cannot be about a meaning or theme of the Quran.

Query: <<<{query}>>>"""


def rerank_prompt(query: str, understood: str, candidates: list[tuple[str, str, str]], lang: str) -> str:
    """candidates: (id, ayah text, tafsir excerpt)"""
    lines = "\n".join(f"[{cid}] {ayah} || {taf}" for cid, ayah, taf in candidates)
    language = "English" if lang == "en" else "Modern Standard Arabic"
    return f"""You are the ranking step of Tadabbur, which finds Quranic ayat that discuss the user's concept.

User query (original): <<<{query}>>>
Understood as: {understood}

Candidates, one per line as [surah:ayah] ayah text || Tafsir al-Muyassar excerpt:
{lines}

Task:
- Choose up to 10 candidates that discuss the concept, best first.
- grade 3 = the ayah addresses the concept directly; 2 = it conveys it implicitly or through a story; 1 = closely related.
- Leave out anything not relevant. If none is relevant, return "no_answer": true with an empty list.
- "why": one sentence of at most 30 words, in {language}, explaining the connection in your own words based on Tafsir al-Muyassar. Never quote or reproduce the ayah text.
- Use only IDs from the candidate list.

Reply with only JSON: {{"no_answer": false, "results": [{{"id": "2:153", "grade": 3, "why": "..."}}]}}"""
