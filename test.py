import requests
import json

BASE_URL = "http://localhost:8000/api"

course_id = "bcf6ce26-72d1-49f0-8083-5542b3f25b65"

chapters = [
    {"chapterId": "chapter_01", "chapterTitle": "Introduction to Python", "subContent": ["What is Python?", "History of Python", "Features of Python", "Setting up Python"]},
    {"chapterId": "chapter_02", "chapterTitle": "Basic Syntax and Data Types", "subContent": ["Variables and Data Types", "Basic Operators", "Control Structures", "Basic Syntax"]},
    {"chapterId": "chapter_03", "chapterTitle": "Control Structures", "subContent": ["If-Else Statements", "For Loops", "While Loops", "Break and Continue Statements"]},
    {"chapterId": "chapter_04", "chapterTitle": "Functions", "subContent": ["Defining Functions", "Function Arguments", "Return Types", "Lambda Functions"]},
    {"chapterId": "chapter_05", "chapterTitle": "Lists and Tuples", "subContent": ["Introduction to Lists", "List Operations", "Introduction to Tuples", "Tuple Operations"]},
    {"chapterId": "chapter_06", "chapterTitle": "Dictionaries and Sets", "subContent": ["Introduction to Dictionaries", "Dictionary Operations", "Introduction to Sets", "Set Operations"]},
    {"chapterId": "chapter_07", "chapterTitle": "File Input/Output and Exceptions", "subContent": ["Reading and Writing Text Files", "Reading and Writing CSV Files", "Handling Exceptions", "Try-Except Blocks"]},
    {"chapterId": "chapter_08", "chapterTitle": "Project and Practice", "subContent": ["Project Ideas", "Best Practices", "Debugging Techniques", "Next Steps"]},
]

def generate_chapter(chapter):
    payload = {
        "course_id": course_id,
        "chapter": chapter,
    }

    print(f"\n{'='*60}")
    print(f"Generating: {chapter['chapterTitle']} ({chapter['chapterId']})")
    print(f"{'='*60}")

    response = requests.post(
        f"{BASE_URL}/generate-video-content",
        json=payload,
        headers={"Content-Type": "application/json"},
         timeout=600,
    )

    print(f"Status: {response.status_code}")

    data = response.json()

    if response.status_code == 200:
        if data.get("skipped"):
            print(f"⏭️  Skipped — content already exists")
        else:
            print(f"✅ Success — {len(data.get('videoContent', []))} slides generated")
    else:
        print(f"❌ Error: {data}")

    return data


if __name__ == "__main__":
    print("Which chapters do you want to generate?")
    print("  all        — generate all 8 chapters")
    print("  1          — generate chapter 1 only")
    print("  1,3,5      — generate specific chapters")

    choice = input("\nEnter choice: ").strip().lower()

    if choice == "all":
        selected = chapters
    else:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        selected = [chapters[i] for i in indices if 0 <= i < len(chapters)]

    print(f"\n🚀 Generating {len(selected)} chapter(s) for course: {course_id}")

    for chapter in selected:
        generate_chapter(chapter)

    print(f"\n✨ Done!")