import { currentUser } from "@clerk/nextjs/server";
import axios from "axios";
import { error } from "console";
import { NextRequest, NextResponse } from "next/server";

const PYTHON_API =
  process.env.NEXT_PUBLIC_PYTHON_API_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const courseId = req.nextUrl.searchParams.get("courseId");
  try {
    if (courseId) {
      const result = await axios.get(`${PYTHON_API}/api/courses/${courseId}`, {
        headers: {
          "x-user-email": user.primaryEmailAddress?.emailAddress
        }
      });

      console.log("Course API Result:", result.data);
      return NextResponse.json(result.data);
    } else {
      const result = await axios.get(`${PYTHON_API}/api/courses`, {
        headers: {
          "x-user-email": user.primaryEmailAddress?.emailAddress
        }
      });
   
      return NextResponse.json(result.data);
    }
  } catch (e) {
    return NextResponse.json(
      { error: "Failed to fetch courses ", e },
      { status: 500 }
    );
  }
}


