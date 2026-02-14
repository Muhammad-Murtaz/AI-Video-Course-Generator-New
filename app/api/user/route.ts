import { currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
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

    console.log("Sending to backend:", userData);

    // Use the NEW clerk endpoint
    const response = await fetch("http://localhost:8000/api/signup-clerk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userData),
    });

    const data = await response.json();
    console.log("Backend response:", data);

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Error creating user:", error);
    return NextResponse.json(
      { error: "Failed to create user" },
      { status: 500 }
    );
  }
}