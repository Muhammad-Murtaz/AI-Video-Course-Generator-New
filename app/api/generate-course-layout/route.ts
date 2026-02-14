import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { NextRequest, NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    console.log("Received request to genrerate course layout");
    
    const user = await currentUser();
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json();

    const result = await axios.post(
      `${PYTHON_API}/api/generate-course-layout`,
      body,
      {
        headers: {
          "x-user-email": user.primaryEmailAddress?.emailAddress || ""
        }
      }
    );
    console.log("Python API response:", result.data);
    return NextResponse.json(result.data);
  } catch (e: any) {
    console.error("Course generation error:", e);

    return NextResponse.json(
      {
        error: e.response?.data?.detail || "Failed to generate layout",
        message: e.response?.data?.detail?.message
      },
      { status: e.response?.status || 500 }
    );
  }
}
