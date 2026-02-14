# app/services/langchain_service.py
from typing import Dict
import logging
from langchain.messages import HumanMessage, SystemMessage
from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from app.core.config import settings
from app.services.rate_limiter import gemini_rate_limiter
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_text_from_response(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block["text"]
    return str(content)


def clean_json_string(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try object first
    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        return object_match.group(0).strip()

    array_match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
    if array_match:
        return array_match.group(0).strip()

    return cleaned.strip()


# ✅ ADD this second function for array responses
def clean_json_array_string(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try array first
    array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if array_match:
        return array_match.group(0).strip()

    return cleaned.strip()


class LangchainCourseGeneratorService:
    def __init__(self):

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            temperature=0.7,
            max_tokens=8000,
            api_key=settings.GEMINI_API_KEY,
        )

        self.fallback_llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=8000,
            api_key=settings.GROQ_API_KEY,
        )

    def _invoke_with_fallback(self, messages):
        """Try Gemini first, fallback to Groq if it fails"""
        try:
            logger.info("🔵 Attempting with Gemini...")
            response = self.llm.invoke(messages)
            logger.info("✅ Gemini succeeded")
            return response
        except Exception as e:
            logger.warning(f"⚠️ Gemini failed: {e}")
            logger.info("🟢 Falling back to Groq...")
            try:
                response = self.fallback_llm.invoke(messages)
                logger.info("✅ Groq succeeded")
                return response
            except Exception as groq_error:
                logger.error(f"❌ Groq also failed: {groq_error}")
                raise HTTPException(
                    status_code=500,
                    detail="Both Gemini and Groq failed to generate content",
                )

    @gemini_rate_limiter
    def generate_course_introduction(self, course_layout: Dict):
        system_prompt = """You are a professional course creator. Generate exactly 5-6 highly engaging introduction slides.

**CRITICAL**: Return ONLY a valid JSON array. No explanations, no markdown, no extra text.

Each slide narration should be 500-750 characters to create a comprehensive 3-minute introduction.

Cover these topics in depth:
1. Welcome & Detailed Course Overview
2. Why this topic is critical today (Industry context)
3. (Learning Path) must include a visual step-by-step timeline or numbered roadmap
4. Prerequisites & Target Audience
5. (Projects) must show 2-3 concrete project cards with name + what the student will build
6. Getting Started & Success Tips

JSON format:
[
  {
    "slideId": "intro_01",
    "slideIndex": 0,
    "audioFileName": "intro_slide_01.mp3",
    "narration": {"fullText": "Your 500-750 character professional narration here"},
    "html": "<div class='p-12 bg-gradient-to-br from-blue-600 to-purple-600 text-white min-h-screen flex flex-col justify-center'><h1 class='text-6xl font-bold mb-6'>Welcome to the Course</h1><p class='text-2xl'>Introduction content here</p></div>",
    "revealData": {"elementsToReveal": [{"selector": "h1", "startTime": 0, "duration": 2}, {"selector": "p", "startTime": 2, "duration": 3}]}
  }
]

IMPORTANT:
- Return ONLY the JSON array
- Each narration must be 500-750 characters
- Make HTML visually appealing with modern gradients and large typography
- Include proper reveal animations"""

        user_message = f"Generate introduction slides for this course:\n{json.dumps(course_layout, indent=2)}"
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        response = self._invoke_with_fallback(messages)
        response_text = extract_text_from_response(response.content)
        cleaned_response = clean_json_array_string(response_text)

        try:
            parsed = json.loads(cleaned_response)
            logger.info(f"✅ Course intro parsed: {len(parsed)} slides")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate course introduction: Invalid JSON response",
            )

    @gemini_rate_limiter
    def generate_video_content(self, chapter_details: Dict):
        system_prompt = """You are an expert instructional designer and motion UI engineer.

INPUT (you will receive a single JSON object):
{
  "courseName": string,
  "chapterTitle": string,
  "chapterSlug": string,
  "subContent": string[] // length 1-3, each item becomes 1 slide
}

TASK:
Generate a SINGLE valid JSON ARRAY of slide objects.
Return ONLY JSON (no markdown, no commentary, no extra keys).

SLIDE SCHEMA (STRICT - each slide must match exactly):
{
  "slideId": string,
  "slideIndex": number,
  "title": string,
  "subtitle": string,
  "audioFileName": string,
  "narration": { "fullText": string },
  "html": string,
  "revealData": string[]
}

RULES:
- Total slides MUST equal subContent.length
- slideIndex MUST start at 1 and increment by 1
- slideId MUST be: "{chapterSlug}-{slideIndex}" (example: "intro-setup-01")
- audioFileName MUST be "{chapterSlug}-{slideId}.mp3"
- - narration.fullText MUST be 8-14 sentences (600-1000 characters), written like a real 
  teacher explaining the concept step-by-step. Include: what it is, why it matters, 
  a simple real-world analogy, how it works, and a concrete code example walkthrough.
  Never just name a concept — always explain it as if the student has never seen it before.
- narration text MUST NOT contain reveal tokens or keys (no "r1", "data-reveal", etc.)

REVEAL SYSTEM (VERY IMPORTANT):
- Split narration.fullText into sentences (3-6 sentences total)
- Each sentence maps to one reveal key in order: r1, r2, r3, ...
- revealData MUST be an array of these keys in order (example: ["r1","r2","r3","r4"])
- The HTML MUST include matching elements using data-reveal="r1", data-reveal="r2", etc.
- All reveal elements MUST start hidden using the class "reveal"
- Do NOT add any JS logic for reveal (another system will toggle "is-on" later)

HTML REQUIREMENTS:
- html MUST be a single self-contained HTML string
- MUST include Tailwind CDN: <script src="https://cdn.tailwindcss.com"></script>
- MUST render in an exact 16:9 frame: 1280x720
- Style: dark, clean gradient, professional look
- Use ONLY inline <style> for animations (no external CSS files)
- MUST include the reveal CSS exactly (you may add transitions):
  .reveal { opacity:0; transform:translateY(12px); }
  .reveal.is-on { opacity:1; transform:translateY(0); }

CONTENT EXPECTATIONS (per slide):
- A header showing courseName + chapterTitle
- A big title and descriptive subtitle (not just the concept name — summarize the insight)
- For EVERY concept slide, include ALL of:
  * A 1-2 sentence plain English definition (r1)
  * A real-world analogy or "why this matters" block (r2)
  * A syntax or code example block with inline comments (r3)
  * A breakdown of what each part of the code does (r4)
  * A "common mistake" or "pro tip" callout card (r5)
- Use <pre> or <code> tags styled with a dark terminal theme for code blocks
- Design should feel like a polished tutorial, not a slide title list

OUTPUT VALIDATION:
- Output MUST be valid JSON ONLY
- Output MUST be an array of slide objects matching the strict schema
- No trailing commas, no comments, no extra fields.

Now generate slides for the provided input."""

        user_message = f"{json.dumps(chapter_details, indent=2)}"
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        response = self._invoke_with_fallback(messages)
        response_text = extract_text_from_response(response.content)
        cleaned_response = clean_json_array_string(response_text)

        try:
            parsed = json.loads(cleaned_response)
            logger.info(f"✅ Video content parsed: {len(parsed)} slides")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate video content: Invalid JSON response",
            )

    @gemini_rate_limiter
    def generate_course_layout(self, user_input: str, type: str):
        system_prompt = """You are a course structure generator.

**CRITICAL**: Return ONLY a valid JSON object. No explanations, no markdown, no extra text.

Generate a comprehensive course structure based on the user's input.

JSON format:
{
  "courseName": "Course Title",
  "courseDescription": "Detailed course description",
  "courseId": "UNIQUE_COURSE_ID",
  "level": "Beginner",
  "totalChapters": 8,
  "chapters": [
    {
      "chapterId": "chapter_01",
      "chapterTitle": "Chapter Title",
      "subContent": ["Topic 1", "Topic 2", "Topic 3"]
    }
  ]
}

IMPORTANT:
- Return ONLY the JSON object
- Generate 6-10 chapters for full courses
- Each chapter should have 3-5 sub-content items
- Make courseId unique and descriptive"""

        user_message = f"Course Topic: {user_input}\nCourse Type: {type}"
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        response = self._invoke_with_fallback(messages)
        response_text = extract_text_from_response(response.content)
        cleaned_response = clean_json_string(response_text)

        try:
            parsed = json.loads(cleaned_response)
            logger.info(f"✅ Course layout parsed: {parsed.get('courseName')}")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            raise ValueError(f"Failed to parse course layout: Invalid JSON response")


langchain_generator = LangchainCourseGeneratorService()
