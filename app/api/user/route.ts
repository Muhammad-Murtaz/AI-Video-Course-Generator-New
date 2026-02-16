import { currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";

export async function POST() {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userData = {
    email: user.emailAddresses[0]?.emailAddress,
    username:
      user.username ||
      user.firstName ||
      user.emailAddresses[0]?.emailAddress.split("@")[0],
    clerk_id: user.id,
  };

  try {
    const response = await fetch(`${PYTHON_API}/api/signup-clerk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userData),
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json({ error: "Failed to create user" }, { status: 500 });
  }
}