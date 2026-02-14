import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Course } from "@/type/CourseType";
import { Player } from "@remotion/player";
import { Dot } from "lucide-react";
import React, { ReactNode, useMemo } from "react";

import CourseComposition from "./ChapterVideo";

const FPS = 30;
const DEFAULT_SLIDE_DURATION = FPS * 6;

interface Props {
  course?: Course;
  durationBySlideId: Record<string, number> | null;
}
function CourseChapters({ course, durationBySlideId }: Props) {
  const slides = course?.chapterContentSlide || [];

  const slidesByChapters = useMemo(() => {
    return slides.reduce<Record<string, typeof slides>>((acc, slide) => {
      (acc[slide.chapterId] ??= []).push(slide);
      return acc;
    }, {});
  }, [slides]);

  const chapterDurationMap = useMemo(() => {
    return slides.reduce<Record<string, number>>((acc, slide) => {
      const slideDuration =
        durationBySlideId?.[slide.slideId] || DEFAULT_SLIDE_DURATION;

      acc[slide.chapterId] = (acc[slide.chapterId] ?? 0) + slideDuration;
      return acc;
    }, {});
  }, [slides, durationBySlideId]);
  return (
    <div className="w-full max-w-7xl mx-auto mt-10">
      <h2 className="font-bold text-2xl">Course Preview</h2>
      <h2 className="text-sm text-muted-foreground mb-6">
        Chapters & Short Preview
      </h2>

      <div className="space-y-5">
        {course?.courseLayout.chapters.map((chapter, index) => {
          const chapterSlides = slidesByChapters[chapter.chapterId] ?? [];
          const chapterDuration =
            chapterDurationMap[chapter.chapterId] ?? DEFAULT_SLIDE_DURATION;

          return (
            <div key={index} className="flex items-start gap-5">
              {/* Chapter Number */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div className="w-10 h-10 rounded-2xl bg-primary/20 flex items-center justify-center text-center text-primary font-bold text-sm">
                  {index + 1}
                </div>
              </div>

              {/* Card with Video LEFT and Content RIGHT */}
              <Card className="flex-1">
                <CardHeader>
                  <CardTitle className="text-base md:text-xl">
                    {chapter.chapterTitle}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Grid Layout: Video LEFT, Content RIGHT */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    {/* LEFT - Video Player */}
                    <div className="rounded-xl overflow-hidden border border-gray-200">
                      <Player
                        component={CourseComposition}
                        durationInFrames={chapterDuration}
                        compositionWidth={1920}
                        compositionHeight={1080}
                        fps={30}
                        inputProps={{
                          slides: chapterSlides,
                          durationBySlideId: durationBySlideId ?? {} // Provide empty object as fallback
                        }}
                        controls
                        loop
                        style={{
                          width: "100%",
                          aspectRatio: "16/9"
                        }}
                      />
                    </div>

                    {/* RIGHT - Sub Content List */}
                    <div className="space-y-2">
                      {chapter.subContent?.map((content, ci) => (
                        <div key={ci} className="flex items-center gap-2">
                          <Dot className="w-5 h-5 text-primary flex-shrink-0" />
                          <h2 className="text-sm md:text-base">{content}</h2>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CourseChapters;
