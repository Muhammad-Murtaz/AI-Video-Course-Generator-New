import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function POST(req: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { courseId, courseLayout } = await req.json();

  if (!courseId || !courseLayout) {
    return NextResponse.json(
      { error: "Missing required fields: courseId and courseLayout" },
      { status: 400 }
    );
  }

  try {
    const result = await axios.post(
      `${PYTHON_API}/api/generate-course-intro`,
      {
        courseId: courseId,
        courseLayout: courseLayout
      },
      {
        headers: {
          "Content-Type": "application/json",
          "x-user-email": user.primaryEmailAddress?.emailAddress || ""
        },
        timeout: 300000
      }
    );
    console.log("Course Intro :", result.data);
    return NextResponse.json(result.data);
  } catch (e: any) {
    console.error(
      "Course introduction generation error:",
      e.response?.data || e.message
    );
    return NextResponse.json(
      {
        error: "Failed to generate course introduction",
        details: e.response?.data || e.message
      },
      { status: 500 }
    );
  }
}
