"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser, SignInButton } from "@clerk/nextjs";
import axios from "axios";
import { toast } from "sonner";
import { Send, Loader2 } from "lucide-react";
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
  const [retryAfter, setRetryAfter] = useState<number | null>(null);

  // Prevent double-submit (double-click, Enter key race)
  const inFlightRef = useRef(false);

  const isDisabled = loading || !userInput.trim() || retryAfter !== null;

  // ── Retry countdown ───────────────────────────────────────────────────────
  const startRetryCountdown = (seconds: number) => {
    setRetryAfter(seconds);
    const interval = setInterval(() => {
      setRetryAfter((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(interval);
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  };

  // ── Generate ──────────────────────────────────────────────────────────────
  const generate = async () => {
    if (!userInput.trim() || inFlightRef.current) return;

    inFlightRef.current = true;
    setLoading(true);
    setRetryAfter(null);

    const toastId = toast.loading("Generating your course layout…");

    try {
      const courseId = crypto.randomUUID();
      const { data } = await axios.post("/api/generate-course-layout", {
        course_id: courseId,
        user_input: userInput.trim(),
        type
      });

      if (data.message === "max-limit") {
        toast.error(
          "You've reached the free course limit. Upgrade to continue!",
          {
            id: toastId
          }
        );
        return;
      }

      toast.success("Course layout generated!", { id: toastId });
      router.push(`/course/${courseId}`);
    } catch (e: any) {
      const status = e.response?.status;
      const detail = e.response?.data?.detail ?? e.response?.data;

      if (status === 429) {
        const retrySeconds: number = detail?.retry_after ?? 60;
        const msg =
          detail?.message ?? `Too many requests — wait ${retrySeconds}s`;
        toast.error(msg, { id: toastId });
        startRetryCountdown(retrySeconds);
        return;
      }

      if (status === 422) {
        // Pydantic validation error — surface the actual field errors
        const errors: string = Array.isArray(detail)
          ? detail.map((d: any) => `${d.loc?.join(".")}: ${d.msg}`).join(", ")
          : (detail?.message ?? "Invalid request — check your input");
        toast.error(`Validation error: ${errors}`, { id: toastId });
        return;
      }

      const message =
        detail?.message === "max-limit"
          ? "Course limit reached. Upgrade your plan!"
          : (detail?.message ??
            detail?.error ??
            "Something went wrong. Please try again.");

      toast.error(message, { id: toastId });
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  };

  return (
    <section className="flex flex-col items-center mt-16 px-4">
      <h1 className="text-4xl md:text-5xl font-bold text-center leading-tight max-w-3xl">
        AI Powered Educational{" "}
        <span className="text-primary">Video Course</span> Generator
      </h1>
      <p className="text-lg text-muted-foreground text-center mt-4 max-w-2xl">
        Create full video courses with AI — slides, narration, and captions
        automatically generated for you.
      </p>

      {/* Input box */}
      <div className="w-full max-w-xl mt-8 rounded-2xl border bg-background shadow-sm focus-within:ring-2 focus-within:ring-primary/20 transition-shadow">
        <div className="flex items-end gap-2 p-4">
          <textarea
            placeholder="Enter your course topic… e.g. React.js for beginners"
            className="w-full min-h-[80px] resize-none outline-none text-base bg-transparent placeholder:text-muted-foreground"
            value={userInput}
            disabled={loading}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !isDisabled) {
                e.preventDefault();
                generate();
              }
            }}
          />

          {user ? (
            <Button
              size="icon"
              onClick={generate}
              disabled={isDisabled}
              className="flex-shrink-0"
              title={
                retryAfter !== null
                  ? `Rate limited — wait ${retryAfter}s`
                  : undefined
              }
            >
              {loading ? (
                <Loader2 className="animate-spin w-4 h-4" />
              ) : retryAfter !== null ? (
                <span className="text-xs font-mono leading-none">
                  {retryAfter}s
                </span>
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          ) : (
            <SignInButton mode="modal">
              <Button size="icon" className="flex-shrink-0">
                <Send className="w-4 h-4" />
              </Button>
            </SignInButton>
          )}
        </div>

        <div className="border-t px-4 py-2 flex items-center justify-between">
          <Select value={type} onValueChange={setType} disabled={loading}>
            <SelectTrigger className="w-[200px] border-0 shadow-none h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="full-course">Full Course</SelectItem>
              <SelectItem value="quick-explain-video">
                Quick Explain Video
              </SelectItem>
            </SelectContent>
          </Select>

          {retryAfter !== null && (
            <p className="text-xs text-muted-foreground animate-pulse">
              Rate limited — try again in {retryAfter}s
            </p>
          )}
        </div>
      </div>

      {/* Quick suggestions */}
      <div className="flex flex-wrap gap-2 mt-5 max-w-2xl justify-center">
        {QUICK_VIDEO_SUGGESTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => !loading && setUserInput(s.prompt)}
            disabled={loading}
            className="border rounded-full px-4 py-1.5 text-xs cursor-pointer hover:bg-muted transition-colors bg-background text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {s.title}
          </button>
        ))}
      </div>
    </section>
  );
}
