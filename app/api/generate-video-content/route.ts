import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { NextRequest, NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { chapter?: unknown; courseId?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { chapter, courseId } = body;

  if (!chapter || !courseId) {
    return NextResponse.json(
      { error: "Missing required fields: chapter and courseId" },
      { status: 400 }
    );
  }

  try {
    const result = await axios.post(
      `${PYTHON_API}/api/generate-video-content`,
      {
        chapter, // dict — passed as-is
        course_id: courseId // ← camelCase from frontend → snake_case for Python schema
      },
      {
        headers: {
          "Content-Type": "application/json",
          "x-user-email": user.primaryEmailAddress?.emailAddress ?? ""
        },
        timeout: 300_000 // 5 min — video gen is slow
      }
    );
    return NextResponse.json(result.data);
  } catch (e: any) {
    const status: number = e.response?.status ?? 500;
    const detail = e.response?.data?.detail ?? e.response?.data;

    if (status === 429) {
      const retryAfter = e.response?.headers?.["retry-after"] ?? "60";
      return NextResponse.json(
        {
          detail: {
            error: "rate_limit_exceeded",
            message: `Too many requests. Try again in ${retryAfter}s.`,
            retry_after: parseInt(retryAfter, 10)
          }
        },
        { status: 429, headers: { "Retry-After": retryAfter } }
      );
    }

    if (status === 422) {
      // Surface Pydantic validation errors for debugging
      return NextResponse.json(
        { error: "Validation error", detail },
        { status: 422 }
      );
    }

    return NextResponse.json(
      { error: detail?.message ?? "Failed to generate video content" },
      { status }
    );
  }
}
