"use client";
import { Sparkles, BarChart2Icon, BookOpen } from "lucide-react";
import { Player } from "@remotion/player";
import CourseComposition from "./ChapterVideo";
import { Course } from "@/type/CourseType";

const FPS = 30;

interface Props {
  course: Course;
  durationBySlideId: Record<string, number> | null;
  durationInFrames: number;
}

export default function CourseInfoCard({
  course,
  durationBySlideId,
  durationInFrames
}: Props) {
  const introSlides = course.courseIntroSlides || [];

  return (
    <div className="max-w-6xl w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-gradient-to-br from-slate-950 via-slate-800 to-emerald-950 rounded-2xl p-20 text-white border border-gray-400/40">
          <h2 className="inline-flex items-center gap-2 px-2 py-1 border border-gray-400/40 rounded-2xl text-sm">
            <Sparkles className="w-4 h-4" /> Course Preview
          </h2>
          <h2 className="text-5xl font-bold mt-4">
            {course.courseLayout?.courseName}
          </h2>
          <p className="text-lg text-gray-300 mt-3">
            {course.courseLayout?.courseDescription}
          </p>
          <div className="flex gap-5 mt-5 flex-wrap">
            <h2 className="inline-flex items-center gap-2 px-3 py-2 border border-gray-400/40 rounded text-white">
              <BarChart2Icon className="w-5 h-5 text-sky-400" />
              {course.courseLayout?.level}
            </h2>
            <h2 className="inline-flex items-center gap-2 px-3 py-2 border border-gray-400/40 rounded text-white">
              <BookOpen className="w-5 h-5 text-emerald-400" />
              {course.courseLayout?.totalChapters} Chapters
            </h2>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center">
          {durationBySlideId && introSlides.length > 0 ? (
            <Player
              component={CourseComposition}
              durationInFrames={durationInFrames || 30}
              compositionWidth={1280}
              compositionHeight={720}
              fps={FPS}
              style={{ width: "100%", aspectRatio: "16/9" }}
              className="border-2 border-white/10 rounded-2xl"
              controls
              inputProps={{ slides: introSlides, durationBySlideId }}
            />
          ) : (
            <div className="w-full aspect-video bg-gray-100 rounded-2xl border flex items-center justify-center">
              <p className="text-gray-400">
                {introSlides.length === 0
                  ? "Generating intro..."
                  : "Loading player..."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
