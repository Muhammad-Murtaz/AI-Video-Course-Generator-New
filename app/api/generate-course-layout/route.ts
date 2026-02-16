import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { NextRequest, NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    const result = await axios.post(
      `${PYTHON_API}/api/generate-course-layout`,
      body,
      {
        headers: {
          "Content-Type": "application/json",
          "x-user-email": user.primaryEmailAddress?.emailAddress ?? ""
        },
        timeout: 60000
      }
    );
    return NextResponse.json(result.data);
  } catch (e: any) {
    const status: number = e.response?.status ?? 500;
    const detail = e.response?.data?.detail ?? e.response?.data;

    // 429 — forward Retry-After header so frontend can display countdown
    if (status === 429) {
      const retryAfter = e.response?.headers?.["retry-after"] ?? "60";
      return NextResponse.json(
        {
          detail: {
            error: "rate_limit_exceeded",
            message:
              detail?.message ??
              `Too many requests. Try again in ${retryAfter}s.`,
            retry_after: parseInt(retryAfter, 10)
          }
        },
        {
          status: 429,
          headers: { "Retry-After": retryAfter }
        }
      );
    }

    // 422 — forward Pydantic validation errors verbatim
    if (status === 422) {
      return NextResponse.json({ detail }, { status: 422 });
    }

    // 403 max-limit
    if (status === 403) {
      return NextResponse.json(
        { message: "max-limit", detail },
        { status: 403 }
      );
    }

    return NextResponse.json(
      { error: detail ?? "Failed to generate course layout" },
      { status }
    );
  }
}
