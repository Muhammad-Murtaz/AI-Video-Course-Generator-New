"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser, SignInButton } from "@clerk/nextjs";
import axios from "axios";
import { toast } from "sonner";
import { Send, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { QUICK_VIDEO_SUGGESTIONS } from "@/data/constants";

export default function Hero() {
  const { user } = useUser();
  const router = useRouter();
  const [userInput, setUserInput] = useState("");
  const [type, setType] = useState("full-course");
  const [loading, setLoading] = useState(false);

  const generateCourseLayout = async () => {
    if (!userInput.trim()) {
      toast.error("Please enter a course topic");
      return;
    }

    setLoading(true);
    const toastId = toast.loading("Generating your course layout...");

    try {
      const courseId = crypto.randomUUID();

      const { data } = await axios.post("/api/generate-course-layout", {
        course_id: courseId,
        user_input: userInput,
        type
      });
      console.log("Course layout :", data);
      if (data.message === "max-limit") {
        toast.error("Maximum courses created. Try monthly plan!", {
          id: toastId
        });
        return;
      }

      toast.success("Course layout generated successfully!", { id: toastId });
      router.push(`/course/${courseId}`);
    } catch (error: any) {
      console.error("Error generating course layout:", error);

      const errorMessage =
        error.response?.data?.message === "max-limit"
          ? "Maximum courses created. Try monthly plan!"
          : error.response?.data?.error || "Something went wrong!";

      toast.error(errorMessage, { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center mt-20">
      <h2 className="text-4xl font-bold text-center">
        AI Powered Educational{" "}
        <span className="text-primary">Video Course</span> Generator
      </h2>
      <p className="text-xl text-center text-gray-500 mt-3">
        Create full video courses with AI — slides, narration, and captions
        automatically generated for you.
      </p>

      <div className="max-w-xl w-full mt-5 rounded-2xl border bg-white z-10">
        <div className="flex items-end gap-2 p-3">
          <textarea
            placeholder="Enter your course topic..."
            className="w-full min-h-[80px] resize-none outline-none text-base bg-transparent"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                generateCourseLayout();
              }
            }}
          />
          <div className="flex flex-col gap-2">
            {user ? (
              <Button
                size="icon"
                onClick={generateCourseLayout}
                disabled={loading || !userInput.trim()}
              >
                {loading ? <Loader className="animate-spin" /> : <Send />}
              </Button>
            ) : (
              <SignInButton mode="modal">
                <Button size="icon">
                  <Send />
                </Button>
              </SignInButton>
            )}
          </div>
        </div>
        <div className="border-t px-3 py-2">
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="w-[200px] border-0 shadow-none">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="full-course">Full Course</SelectItem>
              <SelectItem value="quick-explain-video">
                Quick Explain Video
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mt-5 max-w-3xl justify-center z-10">
        {QUICK_VIDEO_SUGGESTIONS.map((s, i) => (
          <div
            key={i}
            onClick={() => setUserInput(s.prompt)}
            className="border rounded-2xl px-3 py-1 text-sm cursor-pointer hover:bg-gray-100 bg-white"
          >
            {s.title}
          </div>
        ))}
      </div>
    </div>
  );
}
