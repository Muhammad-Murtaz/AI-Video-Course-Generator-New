import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { NextRequest, NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  try {
    const user = await currentUser();
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const email = user.primaryEmailAddress?.emailAddress;

    // Fix: Use consistent parameter name
    const courseId =
      req.nextUrl.searchParams.get("course_id") ||
      req.nextUrl.searchParams.get("courseId");

    if (courseId) {
      // Single course request
      const result = await axios.get(`${PYTHON_API}/api/courses/${courseId}`, {
        headers: { "x-user-email": email }
      });
      return NextResponse.json(result.data.course || result.data);
    }

    // All courses request
    const result = await axios.get(`${PYTHON_API}/api/courses`, {
      headers: { "x-user-email": email }
    });
    return NextResponse.json(result.data.courses || result.data);
  } catch (e: any) {
    console.error("API Error:", e.response?.data || e.message);
    return NextResponse.json(
      { error: e.response?.data?.detail || "Failed to fetch courses" },
      { status: e.response?.status || 500 }
    );
  }
}
