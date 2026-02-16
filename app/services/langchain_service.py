from typing import Dict, List, Type
import logging
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import settings
from pydantic import BaseModel

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
    revealData: List[str]


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


# ── Service ───────────────────────────────────────────────────────────────────


class LangchainCourseGeneratorService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            temperature=0.7,
            max_tokens=16000,
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
            schema_hint = (
                "\n\nReturn ONLY a single valid JSON object matching this exact schema "
                "(no extra wrapper keys, no markdown fences):\n"
                f"{json.dumps(pydantic_schema.model_json_schema(), indent=2)}"
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

            parsed = json.loads(clean_json_string(raw_text))
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
                    "Return a JSON object with a 'slides' array of 5-6 introduction slides.\n"
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
                    "You are an expert instructional designer and motion UI engineer.\n\n"
                    "INPUT:\n"
                    "{\n"
                    '  "courseName": string,\n'
                    '  "chapterTitle": string,\n'
                    '  "chapterSlug": string,\n'
                    '  "subContent": string[]\n'
                    "}\n\n"
                    "TASK:\n"
                    "For EVERY subContent item generate exactly 3 slides (A, B, C).\n"
                    "Total slides = subContent.length × 3.\n"
                    "Return ONLY a flat JSON array. No markdown, no wrapper keys.\n\n"
                    "STRICT SLIDE SCHEMA:\n"
                    "{\n"
                    '  "slideId": "{chapterSlug}-{slideIndex}",\n'
                    '  "slideIndex": number (starts at 1, increments across ALL slides),\n'
                    '  "title": string,\n'
                    '  "subtitle": string,\n'
                    '  "audioFileName": "{chapterSlug}-{slideId}.mp3",\n'
                    '  "narration": { "fullText": string },\n'
                    '  "html": string,\n'
                    '  "revealData": ["r1","r2","r3","r4",...]\n'
                    "}\n\n"
                    "NARRATION RULES:\n"
                    "  8-14 sentences, 600-1000 characters.\n"
                    "  Slide A: explain what it is, why it matters, real-world analogy, how it works.\n"
                    "  Slide B: walk through the code line by line, explain every line.\n"
                    "  Slide C: recap 3 key takeaways verbally, end with a challenge question.\n"
                    "  Write like a teacher talking to a beginner — never just name a concept.\n"
                    "  NO reveal tokens in narration text (no r1, r2, data-reveal).\n\n"
                    "REVEAL SYSTEM:\n"
                    "  revealData = ['r1','r2','r3',...] — one key per narration sentence group.\n"
                    "  Every revealed HTML element MUST have: class='reveal' data-reveal='rN'.\n"
                    "  No JS needed — external system adds 'is-on' class to show elements.\n"
                    "  CSS MUST be in inline <style>:\n"
                    "    .reveal{opacity:0;transform:translateY(16px);transition:opacity 0.5s ease,transform 0.5s ease}\n"
                    "    .reveal.is-on{opacity:1;transform:translateY(0)}\n\n"
                    "HTML RULES (renders in React Remotion 1280x720):\n"
                    "  - Single self-contained HTML string.\n"
                    "  - Root: <div style='width:1280px;height:720px;overflow:hidden;position:relative'>\n"
                    "  - Include: <script src='https://cdn.tailwindcss.com'></script>\n"
                    "  - ALL meaningful content MUST be visible as text on screen.\n"
                    "  - DO NOT put content only in narration — the slide must SHOW it visually.\n"
                    "  - Every concept, every code line, every takeaway MUST appear as rendered text.\n\n"
                    "═══════════════════════════════════════════════\n"
                    "SLIDE A — CONCEPT SLIDE (what + why + analogy)\n"
                    "═══════════════════════════════════════════════\n"
                    "Layout: full dark gradient bg (slate-900 → blue-950), padding 48px.\n"
                    "  TOP ROW: courseName (text-sm uppercase tracking-widest text-blue-300) | chapterTitle (text-sm text-white/50)\n"
                    "  HERO: concept title (text-6xl font-black text-white, reveals as r1) + subtitle (text-xl text-blue-200, reveals as r2)\n"
                    "  DEFINITION BOX (r3): rounded-2xl bg-white/10 backdrop-blur p-6 border-l-4 border-blue-400\n"
                    "    Show the FULL definition as 2-3 sentences of white text. Not just a label.\n"
                    "  CARDS ROW (r4, r5...): 3 cards side by side, each card MUST contain:\n"
                    "    - Icon (emoji or SVG)\n"
                    "    - Bold label (e.g. 'Why it matters')\n"
                    "    - 2-3 sentences of actual explanation text (text-sm text-white/80)\n"
                    "    Card style: rounded-2xl bg-white/10 backdrop-blur border border-white/20 p-5\n"
                    "  ANALOGY BOX (last reveal): rounded-2xl bg-amber-500/20 border border-amber-400/40 p-5\n"
                    "    Show '💡 Real-world analogy:' label + 2-3 sentences explaining the analogy in plain English.\n\n"
                    "═══════════════════════════════════════════════\n"
                    "SLIDE B — CODE SLIDE (real code + walkthrough)\n"
                    "═══════════════════════════════════════════════\n"
                    "Layout: split — LEFT 38% explanation, RIGHT 62% code. Full dark bg (gray-950).\n"
                    "  LEFT PANEL (bg-gray-900, h-full, p-8):\n"
                    "    Title (text-3xl font-black text-white, r1)\n"
                    "    Subtitle (text-base text-gray-400, r1)\n"
                    "    Numbered steps — each step reveals separately (r2, r3, r4...):\n"
                    "      Circle badge (bg-blue-500 text-white font-bold w-8 h-8 rounded-full)\n"
                    "      Step title in bold white\n"
                    "      Step description: 2 sentences explaining what this line does and why\n"
                    "  RIGHT PANEL (bg-gray-950, h-full, p-8, font-mono):\n"
                    "    Code block header: language label (text-xs text-gray-500) + filename\n"
                    "    FULL CODE: every line shown as real syntax-highlighted text.\n"
                    "      Use <span> colors: keywords=text-purple-400, strings=text-green-400,\n"
                    "      numbers=text-yellow-300, comments=text-gray-500, functions=text-blue-300\n"
                    "    Each code section that matches a step gets highlighted with bg-yellow-400/20\n"
                    "    and the reveal class matching that step (r2, r3...).\n"
                    "    OUTPUT BOX (last reveal, rN): bg-black/60 rounded-xl p-4 mt-4\n"
                    "      Label: 'Output:' in text-gray-400 text-xs\n"
                    "      Show the ACTUAL printed output in text-cyan-300 font-mono text-sm\n\n"
                    "═══════════════════════════════════════════════\n"
                    "SLIDE C — RECAP SLIDE (written takeaways + quiz)\n"
                    "═══════════════════════════════════════════════\n"
                    "Layout: dark bg with radial teal/purple gradient. padding 48px.\n"
                    "  TOP: '✅ Chapter Recap' (text-5xl font-black text-white, r1)\n"
                    "       Subtitle: chapter topic in text-xl text-white/60 (r1)\n"
                    "  TAKEAWAY CARDS — 3 cards, each reveals separately (r2, r3, r4):\n"
                    "    Card style: rounded-2xl bg-gradient-to-r from-green-900/50 to-emerald-900/30\n"
                    "                border-l-4 border-green-400 p-5 mb-3\n"
                    "    Each card MUST show:\n"
                    "      ✅ icon + bold takeaway title (text-lg font-bold text-green-300)\n"
                    "      2-3 sentences written explanation of WHY this takeaway matters (text-sm text-white/80)\n"
                    "      A SHORT code snippet or example inline (text-xs font-mono text-yellow-300 bg-black/30 rounded px-2)\n"
                    "  CHALLENGE BOX (r5 — last reveal):\n"
                    "    Style: rounded-2xl bg-amber-500/20 border-2 border-amber-400/50 p-6\n"
                    "    '🧠 Try it yourself:' label (text-sm font-bold text-amber-300 uppercase tracking-wide)\n"
                    "    The challenge question in text-xl font-semibold text-white (full sentence, specific task)\n"
                    "    A hint line: 'Hint: ...' in text-sm text-amber-200/70 italic\n\n"
                    "CRITICAL CONTENT RULES:\n"
                    "  1. EVERY slide MUST display its educational content as VISIBLE TEXT on screen.\n"
                    "  2. Narration and HTML content must MATCH — if narration explains X, the slide must SHOW X.\n"
                    "  3. Code on Slide B MUST be real, runnable, topic-specific code — not placeholder comments.\n"
                    "  4. Takeaway cards on Slide C MUST contain written explanations, not just titles.\n"
                    "  5. Never use lorem ipsum, never use placeholder text.\n"
                    "  6. If subContent topic is 'Python Lists', show actual list syntax, actual list methods, actual output.\n\n"
                    "OUTPUT: valid flat JSON array only. No trailing commas, no comments, no extra fields.\n"
                )
            ),
            HumanMessage(content=json.dumps(chapter_details, indent=2)),
        ]
        result = self._invoke_with_fallback(messages, VideoSlidesOutput)
        return [s.model_dump() for s in result.slides]


langchain_generator = LangchainCourseGeneratorService()
