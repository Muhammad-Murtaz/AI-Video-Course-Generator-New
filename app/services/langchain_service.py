# app/services/langchain_service.py
from typing import Dict, List
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import settings
from pydantic import BaseModel, Field
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────


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


# ─────────────────────────────────────────────
# JSON cleaning (only used for Groq fallback)
# ─────────────────────────────────────────────


def _extract_json_object(raw: str) -> str:
    raw = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return match.group(0).strip() if match else raw.strip()


def _extract_json_array(raw: str) -> str:
    raw = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    return match.group(0).strip() if match else raw.strip()


# ─────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────


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

    def _invoke_with_fallback(
        self,
        messages: list,
        pydantic_schema: BaseModel,
        groq_response_type: str = "object",  # "object" or "array"
        groq_array_key: str = "slides",  # key wrapping array in Groq JSON response
    ):
        """
        Strategy:
        - Gemini: .with_structured_output(pydantic_schema) — forced structured output
        - Groq fallback: JSON mode with explicit schema instructions in prompt, then validate with Pydantic
        """

        # ── 1. Try Gemini with structured output ──
        try:
            logger.info("🔵 Attempting Gemini with structured output...")
            structured_llm = self.llm.with_structured_output(pydantic_schema)
            result = structured_llm.invoke(messages)
            logger.info("✅ Gemini structured output succeeded")
            return result
        except Exception as e:
            logger.warning(f"⚠️ Gemini failed: {e}")

        # ── 2. Groq fallback: JSON mode ──
        logger.info("🟢 Falling back to Groq (JSON mode)...")
        try:
            groq_json_llm = self.fallback_llm.bind(
                response_format={"type": "json_object"}
            )

            # Inject schema hint into the last user message
            schema_hint = f"\n\nReturn ONLY valid JSON matching this schema:\n{json.dumps(pydantic_schema.model_json_schema(), indent=2)}"
            augmented_messages = list(messages)
            last = augmented_messages[-1]
            augmented_messages[-1] = HumanMessage(content=last.content + schema_hint)

            response = groq_json_llm.invoke(augmented_messages)
            raw_text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )

            # Parse and validate via Pydantic
            parsed_dict = json.loads(_extract_json_object(raw_text))

            # Handle case where Groq wraps array in a key (e.g. {"slides": [...]})
            if groq_response_type == "array" and isinstance(parsed_dict, dict):
                # Try common wrapper keys
                for key in [groq_array_key, "slides", "chapters", "data", "items"]:
                    if key in parsed_dict and isinstance(parsed_dict[key], list):
                        parsed_dict = {groq_array_key: parsed_dict[key]}
                        break

            result = pydantic_schema.model_validate(parsed_dict)
            logger.info("✅ Groq JSON mode succeeded")
            return result

        except Exception as groq_error:
            logger.error(f"❌ Groq also failed: {groq_error}")
            raise HTTPException(
                status_code=500,
                detail="Both Gemini and Groq failed to generate content",
            )

    # ─────────────────────────────────────────
    # generate_course_layout
    # ─────────────────────────────────────────
    def generate_course_layout(self, user_input: str, type: str):
        system_prompt = """You are a course structure generator.
Generate a comprehensive course structure based on the user's input.
- Generate 6-10 chapters for full courses
- Each chapter should have 3-5 sub-content items
- Make courseId unique and descriptive (snake_case)"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Course Topic: {user_input}\nCourse Type: {type}"),
        ]

        result: CourseLayoutOutput = self._invoke_with_fallback(
            messages,
            CourseLayoutOutput,
            groq_response_type="object",
        )
        parsed = result.model_dump()
        logger.info(f"✅ Course layout generated: {parsed.get('courseName')}")
        return parsed

    # ─────────────────────────────────────────
    # generate_course_introduction
    # ─────────────────────────────────────────
    def generate_course_introduction(self, course_layout: Dict):
        system_prompt = """You are a professional course creator. Generate exactly 5-6 highly engaging introduction slides.

Each slide narration should be 500-750 characters.

Cover these topics:
1. Welcome & Course Overview
2. Why this topic is critical today
3. Learning Path (visual step-by-step timeline)
4. Prerequisites & Target Audience
5. Projects (2-3 concrete project cards)
6. Getting Started & Success Tips

Return a JSON object with a "slides" array containing 5-6 slide objects.
Each slide: slideId, slideIndex, audioFileName, narration (fullText), html, revealData (elementsToReveal array).
Make HTML visually appealing with Tailwind, modern gradients, large typography."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Generate introduction slides for:\n{json.dumps(course_layout, indent=2)}"
            ),
        ]

        result: IntroSlidesOutput = self._invoke_with_fallback(
            messages,
            IntroSlidesOutput,
            groq_response_type="array",
            groq_array_key="slides",
        )
        parsed = [s.model_dump() for s in result.slides]
        logger.info(f"✅ Course intro generated: {len(parsed)} slides")
        return parsed

    # ─────────────────────────────────────────
    # generate_video_content
    # ─────────────────────────────────────────
    def generate_video_content(self, chapter_details: Dict):
        system_prompt = """You are an expert instructional designer.

INPUT:
{
  "courseName": string,
  "chapterTitle": string,
  "chapterSlug": string,
  "subContent": string[]  // each item = 1 slide
}

Return a JSON object with a "slides" array. Each slide object:
- slideId: "{chapterSlug}-{slideIndex}"
- slideIndex: starts at 1
- title, subtitle
- audioFileName: "{chapterSlug}-{slideId}.mp3"
- narration.fullText: 8-14 sentences, teacher-style explanation
- revealData: ["r1","r2","r3","r4","r5"]
- html: self-contained HTML (1280x720, dark theme, Tailwind CDN, reveal CSS)
  .reveal { opacity:0; transform:translateY(12px); }
  .reveal.is-on { opacity:1; transform:translateY(0); }
  Elements use data-reveal="r1" etc., start with class "reveal"

Per slide include: definition (r1), analogy (r2), code example (r3), code breakdown (r4), pro tip (r5)."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(chapter_details, indent=2)),
        ]

        result: VideoSlidesOutput = self._invoke_with_fallback(
            messages,
            VideoSlidesOutput,
            groq_response_type="array",
            groq_array_key="slides",
        )
        parsed = [s.model_dump() for s in result.slides]
        logger.info(f"✅ Video content generated: {len(parsed)} slides")
        return parsed


langchain_generator = LangchainCourseGeneratorService()
