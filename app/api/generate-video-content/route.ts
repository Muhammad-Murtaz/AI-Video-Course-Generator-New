import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { error } from "console";
import { NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";
export async function POST(req: NextResponse) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { chapter, courseId } = await req.json();
  if (!chapter || !courseId) {
    return NextResponse.json(
      { error: "Missing required fields" },
      { status: 400 }
    );
  }
  try {
    const result = await axios.post(
      `${PYTHON_API}/api/generate-video-content`,
      {
        chapter: chapter,
        course_id: courseId
      },
      {
        headers: {
          "x-user-email": user.primaryEmailAddress?.emailAddress || "",
          timeout: 300000
        }
      }
    );
    return NextResponse.json(result.data);
  } catch (e) {
    console.log("Video content generation error:", e);
    return NextResponse.json(
      { error: "Failed to generate video content" },
      { status: 500 }
    );
  }
}
