from typing import Dict, List, Type, Optional
import logging
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import settings
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────


class NarrationModel(BaseModel):
    fullText: str


class RevealElement(BaseModel):
    selector: str
    startTime: int
    duration: int


class RevealData(BaseModel):
    elementsToReveal: List[RevealElement]


class IntroSlide(BaseModel):
    slideId: str
    slideIndex: int
    audioFileName: str
    narration: NarrationModel
    html: str
    revealData: RevealData


class IntroSlidesOutput(BaseModel):
    slides: List[IntroSlide]


class VideoSlide(BaseModel):
    slideId: str
    slideIndex: int
    title: str
    subtitle: str
    audioFileName: str
    narration: NarrationModel
    html: str
    # ── FIX 1: Make revealData optional with a default so truncated JSON
    #    doesn't crash Pydantic validation. A missing field now falls back
    #    to an empty list instead of raising "Field required".
    revealData: Optional[List[str]] = []

    @field_validator("revealData", mode="before")
    @classmethod
    def ensure_list(cls, v):
        """Accept None or missing → empty list; accept a raw list → keep it."""
        if v is None:
            return []
        return v


class VideoSlidesOutput(BaseModel):
    slides: List[VideoSlide]


class ChapterModel(BaseModel):
    chapterId: str
    chapterTitle: str
    subContent: List[str]


class CourseLayoutOutput(BaseModel):
    courseName: str
    courseDescription: str
    courseId: str
    level: str
    totalChapters: int
    chapters: List[ChapterModel]


# ── JSON cleaning ─────────────────────────────────────────────────────────────


def clean_json_string(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def wrap_array_if_needed(raw: str, schema: Type[BaseModel]) -> str:
    """
    FIX 2 (Groq fallback): Gemini is told to return a flat array but
    VideoSlidesOutput expects {"slides": [...]}.
    If the LLM returns a bare JSON array and the schema has a 'slides' key,
    wrap it automatically instead of crashing.
    """
    stripped = raw.strip()
    if stripped.startswith("[") and "slides" in schema.model_fields:
        return json.dumps({"slides": json.loads(stripped)})
    return stripped


# ── Service ───────────────────────────────────────────────────────────────────


class LangchainCourseGeneratorService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",  # use a stable, high-output model
            temperature=0.7,
            max_tokens=20000,  # FIX 3: was 16000 — slides were being cut off mid-JSON
            api_key=settings.GEMINI_API_KEY,
        )
        self.fallback_llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=8000,
            api_key=settings.GROQ_API_KEY,
        )

    def _invoke_with_fallback(self, messages: list, pydantic_schema: Type[BaseModel]):
        # 1. Try Gemini with structured output
        try:
            return self.llm.with_structured_output(pydantic_schema).invoke(messages)
        except Exception as e:
            logger.warning("Gemini failed, falling back to Groq: %s", e)

        # 2. Groq JSON fallback
        try:
            # FIX 4 (token savings): send only field names, not the full JSON schema.
            # The full schema was burning ~2 000 tokens on every fallback call,
            # which rapidly exhausted the Groq daily token limit (100 000 TPD).
            schema_hint = (
                "\n\nReturn ONLY valid JSON. "
                "Top-level keys required: "
                f"{list(pydantic_schema.model_fields.keys())}"
            )
            augmented = list(messages)
            augmented[-1] = HumanMessage(content=messages[-1].content + schema_hint)

            response = self.fallback_llm.bind(
                response_format={"type": "json_object"}
            ).invoke(augmented)

            raw_text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )

            # FIX 2 applied here: auto-wrap bare arrays before validation
            normalised = wrap_array_if_needed(
                clean_json_string(raw_text), pydantic_schema
            )
            parsed = json.loads(normalised)
            return pydantic_schema.model_validate(parsed)

        except Exception as e:
            logger.error("Groq also failed: %s", e)
            raise HTTPException(
                status_code=500, detail="Both AI providers failed to generate content"
            )

    # ── Public methods ────────────────────────────────────────────────────────

    def generate_course_layout(self, user_input: str, type: str) -> dict:
        messages = [
            SystemMessage(
                content=(
                    "You are a course structure generator.\n"
                    "Return a single flat JSON object with these exact fields:\n"
                    "  courseName, courseDescription, courseId (snake_case), level (Beginner|Intermediate|Advanced),\n"
                    "  totalChapters (int), chapters (array: chapterId, chapterTitle, subContent[])\n"
                    "Rules: 6-10 chapters for full-course, 3-5 for quick-explain-video. Each chapter: 3-5 subContent items."
                )
            ),
            HumanMessage(content=f"Course Topic: {user_input}\nCourse Type: {type}"),
        ]
        result = self._invoke_with_fallback(messages, CourseLayoutOutput)
        return result.model_dump()

    def generate_course_introduction(self, course_layout: Dict) -> list:
        messages = [
            SystemMessage(
                content=(
                    "You are a professional course creator.\n"
                    "Return a JSON object with a 'slides' key containing an array of 5-6 introduction slides.\n"
                    "Each slide: slideId, slideIndex, audioFileName, narration (fullText 500-750 chars),\n"
                    "html (Tailwind CDN, dark gradient, large typography), revealData (elementsToReveal array).\n"
                    "Slide topics: Welcome & Overview, Why this topic matters, Learning Path,\n"
                    "Prerequisites & Audience, Projects, Getting Started."
                )
            ),
            HumanMessage(
                content=f"Generate introduction slides for:\n{json.dumps(course_layout, indent=2)}"
            ),
        ]
        result = self._invoke_with_fallback(messages, IntroSlidesOutput)
        return [s.model_dump() for s in result.slides]

    def generate_video_content(self, chapter_details: Dict) -> list:
        messages = [
            SystemMessage(
                content=(
                    """You are an expert instructional designer creating educational video slides.

🚨 ABSOLUTE RULE: Every word in the narration MUST have a matching visual element on the slide.
If you mention an example, SHOW it. If you explain code, DISPLAY it. If you list 3 points, RENDER all 3.

═══════════════════════════════════════════════════════════════════════════════
INPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════
{
  "courseName": string,
  "chapterTitle": string,
  "chapterSlug": string,
  "subContent": [array of topics]
}

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════
{
  "slides": [
    {
      "slideId": "{chapterSlug}-{index}",
      "slideIndex": number,
      "title": string,
      "subtitle": string,
      "audioFileName": "{chapterSlug}-{slideId}.mp3",
      "narration": {
        "fullText": "600-900 character narration matching visual content exactly"
      },
      "html": "Complete HTML string with ALL content visible",
      "revealData": ["r1", "r2", "r3", "r4", "r5", "r6"]
    }
  ]
}

═══════════════════════════════════════════════════════════════════════════════
SLIDE STRUCTURE: 3 SLIDES PER SUBCONTENT TOPIC
═══════════════════════════════════════════════════════════════════════════════

For each subContent topic, create exactly 3 slides:

SLIDE A: CONCEPT EXPLANATION (visual learning)
SLIDE B: CODE DEMONSTRATION (hands-on example)  
SLIDE C: SUMMARY & CHALLENGE (reinforcement)

═══════════════════════════════════════════════════════════════════════════════
SLIDE A: CONCEPT SLIDE
═══════════════════════════════════════════════════════════════════════════════

PURPOSE: Visually explain WHAT the concept is, WHY it matters, and HOW it's used.

NARRATION (8-12 sentences, 650-850 chars):
Sentence 1: "Let's learn about [CONCEPT]."
Sentence 2-3: Define it in simple terms with an analogy
Sentence 4-5: Explain why programmers use it
Sentence 6-7: Give a real-world use case example
Sentence 8-9: List the 3 main benefits
Sentence 10-11: Mention common mistakes
Sentence 12: "Now let's see it in action."

HTML TEMPLATE (MANDATORY - FILL EVERY BRACKET):
```html
<div style="width:1280px;height:720px;display:flex;align-items:center;justify-content:center;padding:60px;background:linear-gradient(135deg,#0f172a,#1e3a5f)">
<script src="https://cdn.tailwindcss.com"></script>
<style>
.reveal{opacity:0;transform:translateY(20px);transition:all 0.6s}
.reveal.is-on{opacity:1;transform:translateY(0)}
</style>

<div style="max-width:1100px;width:100%">

  <!-- HEADER (r1) -->
  <div class="reveal" data-reveal="r1">
    <div style="display:flex;justify-content:space-between;margin-bottom:24px">
      <span style="color:#60a5fa;font-size:13px;text-transform:uppercase;letter-spacing:2px">[COURSE NAME]</span>
      <span style="color:rgba(255,255,255,0.5);font-size:13px">[CHAPTER TITLE]</span>
    </div>
    <h1 style="font-size:64px;font-weight:900;color:white;margin-bottom:16px;line-height:1.1">[CONCEPT TITLE]</h1>
    <p style="font-size:24px;color:#93c5fd">[One-line description]</p>
  </div>

  <!-- DEFINITION BOX (r2) - MUST BE 3-4 SENTENCES -->
  <div class="reveal" data-reveal="r2" style="margin-top:48px;padding:32px;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border-left:4px solid #3b82f6;border-radius:16px">
    <div style="display:flex;align-items:start;gap:24px">
      <span style="font-size:56px">📚</span>
      <div>
        <h3 style="font-size:22px;font-weight:700;color:white;margin-bottom:16px">What is [CONCEPT]?</h3>
        <p style="font-size:18px;color:rgba(255,255,255,0.9);line-height:1.7">
          [WRITE FULL DEFINITION - 3-4 COMPLETE SENTENCES EXPLAINING THE CONCEPT IN DETAIL. NOT JUST ONE LINE!]
        </p>
      </div>
    </div>
  </div>

  <!-- 3 BENEFIT CARDS (r3, r4, r5) - EACH MUST HAVE 2-3 SENTENCES -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:48px">
    
    <div class="reveal" data-reveal="r3" style="padding:28px;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.2);border-radius:16px">
      <div style="font-size:48px;margin-bottom:16px">🎯</div>
      <h4 style="font-size:20px;font-weight:700;color:white;margin-bottom:12px">[Benefit 1 Title]</h4>
      <p style="font-size:15px;color:rgba(255,255,255,0.8);line-height:1.6">
        [WRITE 2-3 SENTENCES EXPLAINING THIS BENEFIT IN DETAIL WITH AN EXAMPLE]
      </p>
    </div>

    <div class="reveal" data-reveal="r4" style="padding:28px;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.2);border-radius:16px">
      <div style="font-size:48px;margin-bottom:16px">⚡</div>
      <h4 style="font-size:20px;font-weight:700;color:white;margin-bottom:12px">[Benefit 2 Title]</h4>
      <p style="font-size:15px;color:rgba(255,255,255,0.8);line-height:1.6">
        [WRITE 2-3 SENTENCES EXPLAINING THIS BENEFIT IN DETAIL WITH AN EXAMPLE]
      </p>
    </div>

    <div class="reveal" data-reveal="r5" style="padding:28px;background:rgba(255,255,255,0.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.2);border-radius:16px">
      <div style="font-size:48px;margin-bottom:16px">🚀</div>
      <h4 style="font-size:20px;font-weight:700;color:white;margin-bottom:12px">[Benefit 3 Title]</h4>
      <p style="font-size:15px;color:rgba(255,255,255,0.8);line-height:1.6">
        [WRITE 2-3 SENTENCES EXPLAINING THIS BENEFIT IN DETAIL WITH AN EXAMPLE]
      </p>
    </div>

  </div>

  <!-- ANALOGY BOX (r6) - MUST BE 3-4 SENTENCES -->
  <div class="reveal" data-reveal="r6" style="margin-top:48px;padding:32px;background:rgba(251,191,36,0.2);border:2px solid rgba(251,191,36,0.4);border-radius:16px">
    <div style="display:flex;align-items:start;gap:24px">
      <span style="font-size:48px">💡</span>
      <div>
        <h3 style="font-size:22px;font-weight:700;color:#fbbf24;margin-bottom:16px">Think of it like this...</h3>
        <p style="font-size:18px;color:white;line-height:1.7">
          [WRITE A FULL REAL-WORLD ANALOGY - 3-4 SENTENCES COMPARING THE CONCEPT TO SOMETHING EVERYONE KNOWS. BE SPECIFIC!]
        </p>
      </div>
    </div>
  </div>

</div>
</div>
```

MANDATORY CONTENT REQUIREMENTS FOR SLIDE A:
✓ Definition box: 60-100 words (3-4 full sentences)
✓ Each benefit card: 30-50 words (2-3 sentences with examples)
✓ Analogy box: 60-90 words (3-4 sentences of detailed comparison)
✓ Total visible text: 250+ words on screen
✓ NO empty boxes, NO single sentences, NO placeholders

═══════════════════════════════════════════════════════════════════════════════
SLIDE B: CODE SLIDE  
═══════════════════════════════════════════════════════════════════════════════

PURPOSE: Show REAL working code with step-by-step explanation of EVERY line.

NARRATION (10-14 sentences, 700-950 chars):
Sentence 1: "Here's a real example using [CONCEPT]."
Sentence 2-11: Explain EACH LINE of code in order (one sentence per line/step)
Sentence 12-13: Explain what the output means
Sentence 14: "Notice how [key insight]."

HTML TEMPLATE (MANDATORY - SPLIT SCREEN):
```html
<div style="width:1280px;height:720px;display:flex;background:#0a0a0f">
<script src="https://cdn.tailwindcss.com"></script>
<style>
.reveal{opacity:0;transform:translateX(-10px);transition:all 0.5s}
.reveal.is-on{opacity:1;transform:translateX(0)}
</style>

<!-- LEFT PANEL: EXPLANATIONS (38%) -->
<div style="width:38%;background:#111827;padding:48px;overflow-y:auto">
  
  <div class="reveal" data-reveal="r1">
    <h2 style="font-size:42px;font-weight:900;color:white;margin-bottom:8px">Code Walkthrough</h2>
    <p style="font-size:16px;color:#9ca3af;margin-bottom:40px">[Subtitle describing what the code does]</p>
  </div>

  <!-- STEP 1 (r2) -->
  <div class="reveal" data-reveal="r2" style="display:flex;gap:16px;margin-bottom:32px">
    <div style="width:40px;height:40px;background:#3b82f6;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <span style="color:white;font-weight:700;font-size:18px">1</span>
    </div>
    <div>
      <h4 style="color:white;font-weight:700;font-size:18px;margin-bottom:8px">[What this step does]</h4>
      <p style="color:#d1d5db;font-size:15px;line-height:1.6">
        [EXPLAIN THIS CODE LINE IN 2-3 SENTENCES: what it does, why it's needed, what happens]
      </p>
    </div>
  </div>

  <!-- STEP 2 (r3) -->
  <div class="reveal" data-reveal="r3" style="display:flex;gap:16px;margin-bottom:32px">
    <div style="width:40px;height:40px;background:#3b82f6;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <span style="color:white;font-weight:700;font-size:18px">2</span>
    </div>
    <div>
      <h4 style="color:white;font-weight:700;font-size:18px;margin-bottom:8px">[What this step does]</h4>
      <p style="color:#d1d5db;font-size:15px;line-height:1.6">
        [EXPLAIN THIS CODE LINE IN 2-3 SENTENCES]
      </p>
    </div>
  </div>

  <!-- CONTINUE FOR ALL CODE STEPS (r4, r5, r6...) -->
  <!-- MINIMUM 5 STEPS, MAXIMUM 8 STEPS -->

</div>

<!-- RIGHT PANEL: ACTUAL CODE (62%) -->
<div style="width:62%;background:#0f0f1a;padding:48px;overflow-y:auto;font-family:'Courier New',monospace">
  
  <!-- CODE HEADER -->
  <div style="display:flex;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid #374151;margin-bottom:24px">
    <span style="color:#6b7280;font-size:12px;text-transform:uppercase">Python</span>
    <span style="color:#4b5563;font-size:12px">example.py</span>
  </div>

  <!-- ACTUAL CODE - SHOW EVERY LINE WITH SYNTAX HIGHLIGHTING -->
  <!-- Keywords: #a78bfa (purple), Strings: #4ade80 (green), Numbers: #fbbf24 (yellow), 
       Functions: #60a5fa (blue), Comments: #6b7280 (gray), Variables: #fb923c (orange) -->

  <div style="font-size:17px;line-height:1.9">
    
    <!-- Line 1 - Links to step 1 (r2) -->
    <div class="reveal" data-reveal="r2" style="background:rgba(251,191,36,0.1);padding:4px 0">
      <span style="color:#6b7280">1</span>
      <span style="color:#a78bfa;margin-left:16px">def</span>
      <span style="color:#60a5fa"> calculate_sum</span>
      <span style="color:#fbbf24">(</span>
      <span style="color:#fb923c">numbers</span>
      <span style="color:#fbbf24">):</span>
    </div>

    <!-- Line 2 - Links to step 2 (r3) -->
    <div class="reveal" data-reveal="r3" style="background:rgba(251,191,36,0.1);padding:4px 0">
      <span style="color:#6b7280">2</span>
      <span style="color:#6b7280;margin-left:32px"># Initialize total variable</span>
    </div>

    <!-- Line 3 - Links to step 2 (r3) -->
    <div class="reveal" data-reveal="r3" style="background:rgba(251,191,36,0.1);padding:4px 0">
      <span style="color:#6b7280">3</span>
      <span style="color:#fb923c;margin-left:32px">total</span>
      <span style="color:white"> = </span>
      <span style="color:#fbbf24">0</span>
    </div>

    <!-- CONTINUE FOR EVERY SINGLE LINE OF CODE -->
    <!-- EACH LINE MUST BE REAL, RUNNABLE CODE -->
    <!-- MINIMUM 8 LINES, MAXIMUM 15 LINES -->

    <!-- OUTPUT BOX (last reveal) -->
    <div class="reveal" data-reveal="r8" style="margin-top:32px;padding:24px;background:rgba(0,0,0,0.6);border:1px solid rgba(34,211,238,0.3);border-radius:12px">
      <div style="color:#6b7280;font-size:12px;text-transform:uppercase;margin-bottom:12px">Output:</div>
      <div style="color:#22d3ee;font-size:16px;font-family:'Courier New',monospace">
[SHOW THE ACTUAL OUTPUT - WHAT THE CODE PRINTS/RETURNS]
Example: 
The sum is: 15
[4, 8, 3] sorted: [3, 4, 8]
      </div>
    </div>

  </div>

</div>

</div>
```

MANDATORY CONTENT REQUIREMENTS FOR SLIDE B:
✓ Minimum 5 explanation steps, maximum 8 steps
✓ Each step explanation: 40-60 words (2-3 sentences)
✓ Code must be 8-15 lines of REAL, RUNNABLE code (not comments or pseudo-code)
✓ Every line of code must have matching explanation
✓ Output box must show the ACTUAL result
✓ Code must be syntactically correct and topic-specific
✓ NO placeholder code like "# Your code here"
✓ Total visible text: 300+ words on screen

EXAMPLE BAD CODE (NEVER DO THIS):
```python
# Step 1: Do something
# Step 2: Do something else
# Add your code here
```

EXAMPLE GOOD CODE (ALWAYS DO THIS):
```python
def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    average = total / count
    return average

scores = [85, 92, 78, 95, 88]
result = calculate_average(scores)
print(f"Average score: {result}")
```

═══════════════════════════════════════════════════════════════════════════════
SLIDE C: RECAP SLIDE
═══════════════════════════════════════════════════════════════════════════════

PURPOSE: Reinforce learning with 3 key takeaways (with explanations) and a challenge.

NARRATION (8-10 sentences, 600-800 chars):
Sentence 1: "Let's recap what we learned about [CONCEPT]."
Sentence 2-3: State takeaway 1 and explain why it matters
Sentence 4-5: State takeaway 2 and explain why it matters
Sentence 6-7: State takeaway 3 and explain why it matters
Sentence 8-9: Present the challenge question
Sentence 10: Give a hint

HTML TEMPLATE (MANDATORY):
```html
<div style="width:1280px;height:720px;display:flex;align-items:center;justify-content:center;padding:60px;background:radial-gradient(circle at top right,#1e3a5f 0%,#0a0a0f 50%,#1a1a2e 100%)">
<script src="https://cdn.tailwindcss.com"></script>
<style>
.reveal{opacity:0;transform:scale(0.95);transition:all 0.5s}
.reveal.is-on{opacity:1;transform:scale(1)}
</style>

<div style="max-width:1000px;width:100%">

  <!-- HEADER (r1) -->
  <div class="reveal" data-reveal="r1" style="text-align:center;margin-bottom:48px">
    <h1 style="font-size:68px;font-weight:900;color:white;margin-bottom:16px">✅ Key Takeaways</h1>
    <p style="font-size:26px;color:rgba(255,255,255,0.6)">[Topic Name]</p>
  </div>

  <!-- TAKEAWAY 1 (r2) -->
  <div class="reveal" data-reveal="r2" style="margin-bottom:24px;padding:32px;background:linear-gradient(to right,rgba(16,185,129,0.3),rgba(5,150,105,0.2));border-left:4px solid #10b981;border-radius:16px">
    <div style="display:flex;align-items:start;gap:20px">
      <span style="font-size:40px;flex-shrink:0">✅</span>
      <div style="flex:1">
        <h3 style="font-size:26px;font-weight:700;color:#6ee7b7;margin-bottom:16px">[Takeaway Title 1]</h3>
        <p style="font-size:17px;color:rgba(255,255,255,0.9);line-height:1.7;margin-bottom:16px">
          [WRITE 3-4 SENTENCES EXPLAINING THIS TAKEAWAY IN DETAIL: what it means, why it's important, when to use it, common use case]
        </p>
        <div style="display:inline-block;background:rgba(0,0,0,0.4);padding:8px 16px;border-radius:8px;font-family:'Courier New',monospace">
          <code style="color:#fbbf24;font-size:15px">[real code example here]</code>
        </div>
      </div>
    </div>
  </div>

  <!-- TAKEAWAY 2 (r3) -->
  <div class="reveal" data-reveal="r3" style="margin-bottom:24px;padding:32px;background:linear-gradient(to right,rgba(16,185,129,0.3),rgba(5,150,105,0.2));border-left:4px solid #10b981;border-radius:16px">
    <div style="display:flex;align-items:start;gap:20px">
      <span style="font-size:40px;flex-shrink:0">✅</span>
      <div style="flex:1">
        <h3 style="font-size:26px;font-weight:700;color:#6ee7b7;margin-bottom:16px">[Takeaway Title 2]</h3>
        <p style="font-size:17px;color:rgba(255,255,255,0.9);line-height:1.7;margin-bottom:16px">
          [WRITE 3-4 SENTENCES EXPLAINING THIS TAKEAWAY IN DETAIL]
        </p>
        <div style="display:inline-block;background:rgba(0,0,0,0.4);padding:8px 16px;border-radius:8px;font-family:'Courier New',monospace">
          <code style="color:#fbbf24;font-size:15px">[real code example here]</code>
        </div>
      </div>
    </div>
  </div>

  <!-- TAKEAWAY 3 (r4) -->
  <div class="reveal" data-reveal="r3" style="margin-bottom:40px;padding:32px;background:linear-gradient(to right,rgba(16,185,129,0.3),rgba(5,150,105,0.2));border-left:4px solid #10b981;border-radius:16px">
    <div style="display:flex;align-items:start;gap:20px">
      <span style="font-size:40px;flex-shrink:0">✅</span>
      <div style="flex:1">
        <h3 style="font-size:26px;font-weight:700;color:#6ee7b7;margin-bottom:16px">[Takeaway Title 3]</h3>
        <p style="font-size:17px;color:rgba(255,255,255,0.9);line-height:1.7;margin-bottom:16px">
          [WRITE 3-4 SENTENCES EXPLAINING THIS TAKEAWAY IN DETAIL]
        </p>
        <div style="display:inline-block;background:rgba(0,0,0,0.4);padding:8px 16px;border-radius:8px;font-family:'Courier New',monospace">
          <code style="color:#fbbf24;font-size:15px">[real code example here]</code>
        </div>
      </div>
    </div>
  </div>

  <!-- CHALLENGE BOX (r5) -->
  <div class="reveal" data-reveal="r5" style="padding:36px;background:rgba(251,191,36,0.2);border:2px solid rgba(251,191,36,0.5);border-radius:16px">
    <div style="display:flex;align-items:start;gap:24px">
      <span style="font-size:52px;flex-shrink:0">🧠</span>
      <div style="flex:1">
        <div style="font-size:14px;font-weight:700;color:#fbbf24;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px">Try It Yourself</div>
        <p style="font-size:24px;font-weight:600;color:white;line-height:1.5;margin-bottom:20px">
          [WRITE A SPECIFIC, ACTIONABLE CHALLENGE QUESTION - NOT VAGUE. Example: "Create a function that takes a list of numbers and returns only the even numbers multiplied by 2."]
        </p>
        <p style="font-size:17px;color:rgba(251,191,36,0.8);font-style:italic">
          💡 Hint: [Give a helpful hint that guides without giving the full answer]
        </p>
      </div>
    </div>
  </div>

</div>
</div>
```

MANDATORY CONTENT REQUIREMENTS FOR SLIDE C:
✓ Each takeaway card: 70-100 words (3-4 sentences of detailed explanation)
✓ Each takeaway must include a code snippet (5-15 characters)
✓ Challenge question must be specific and actionable (not "practice variables")
✓ Hint must be helpful (not just "use what you learned")
✓ Total visible text: 350+ words on screen
✓ NO generic statements like "This is important because it helps with coding"
✓ MUST explain exactly WHY and HOW each takeaway matters

═══════════════════════════════════════════════════════════════════════════════
VALIDATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

Before returning slides, verify EACH slide meets these criteria:

SLIDE A (Concept):
□ Definition box: 60-100 words (not 1-2 sentences)
□ Each benefit card: 30-50 words each (not just titles)
□ Analogy box: 60-90 words (not 1 sentence)
□ Total HTML length: 2500+ characters
□ All text is visible white text on dark background

SLIDE B (Code):
□ Has 5-8 explanation steps
□ Each step: 40-60 words
□ Code is 8-15 lines of REAL, runnable code
□ Every line has syntax highlighting
□ Output box shows actual result
□ Total HTML length: 3000+ characters
□ Code is NOT placeholder comments

SLIDE C (Recap):
□ Has exactly 3 takeaway cards
□ Each card: 70-100 words of explanation
□ Each card: has a code snippet
□ Challenge is specific (not vague)
□ Hint is helpful (not generic)
□ Total HTML length: 2800+ characters

GENERAL FOR ALL SLIDES:
□ Narration matches HTML content exactly
□ Every sentence in narration has a visual element
□ No lorem ipsum or placeholders
□ All brackets [...] are replaced with real content
□ revealData array has correct number of items (r1, r2, r3...)
□ HTML is valid (no unclosed tags)
□ Colors use inline styles (no external CSS)
□ Text is large enough to read (16px minimum)

═══════════════════════════════════════════════════════════════════════════════
COMMON MISTAKES TO AVOID
═══════════════════════════════════════════════════════════════════════════════

❌ WRONG: "Variables store data. They are useful. For example, x = 5."
✓ RIGHT: "Variables are named containers that hold data in memory. They let you store values like numbers, text, or complex objects, and reuse them throughout your program without retyping. For example, if you write x = 5, Python creates a variable called x that stores the number 5."

❌ WRONG: Code with comments only:
```python
# Define function
# Add logic here  
# Return result
```

✓ RIGHT: Real working code:
```python
def calculate_total(prices, tax_rate):
    subtotal = sum(prices)
    tax = subtotal * tax_rate
    total = subtotal + tax
    return round(total, 2)
```

❌ WRONG: Takeaway card with just title and one sentence
✓ RIGHT: Takeaway card with title + 3-4 sentences + code example

❌ WRONG: Challenge: "Practice using variables"
✓ RIGHT: Challenge: "Create a function that takes a student's name and three test scores, then returns a formatted string showing their average. For example: 'Alice scored an average of 87.3%'"

═══════════════════════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Return ONLY valid JSON in this exact format:
{
  "slides": [
    {...slide1...},
    {...slide2...},
    {...slide3...}
  ]
}

NO markdown code blocks.
NO comments in JSON.
NO trailing commas.
NO extra wrapper objects.
ONLY the JSON object with "slides" key.

═══════════════════════════════════════════════════════════════════════════════
FINAL REMINDER
═══════════════════════════════════════════════════════════════════════════════

If narration says "For example, we can use a for loop to iterate through a list", 
then the HTML MUST show that exact for loop code.

If narration says "The three main benefits are...", 
then the HTML MUST show all three benefits with full explanations.

If narration says "Here's how to declare a variable",
then the HTML MUST show the actual variable declaration code.

EVERY. WORD. IN. NARRATION. NEEDS. A. VISUAL. MATCH.
"""
                )
            ),
            HumanMessage(content=json.dumps(chapter_details, indent=2)),
        ]

        # Add retry logic with content validation
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = self._invoke_with_fallback(messages, VideoSlidesOutput)

                # Validate each slide has sufficient content
                for slide in result.slides:
                    if len(slide.html) < 1500:
                        raise ValueError(
                            f"Slide {slide.slideId} has insufficient HTML content ({len(slide.html)} chars)"
                        )
                    if len(slide.narration.fullText) < 400:
                        raise ValueError(f"Slide {slide.slideId} narration too short")

                logger.info(f"✅ Generated {len(result.slides)} content-rich slides")
                return [s.model_dump() for s in result.slides]

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying: {e}")
                    continue
                else:
                    logger.error(
                        f"Failed to generate quality content after {max_retries} attempts"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Could not generate sufficient slide content: {str(e)}",
                    )


langchain_generator = LangchainCourseGeneratorService()
