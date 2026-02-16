"use client";
import { Dot, Play, Clock } from "lucide-react";
import { Player } from "@remotion/player";
import { Card, CardContent } from "@/components/ui/card";
import CourseComposition from "./ChapterVideo";
import { Course } from "@/type/CourseType";

const FPS = 30;

interface Props {
  course: Course;
  durationBySlideId: Record<string, number> | null;
  durationInFrames: number;
}

export default function CourseChapters({
  course,
  durationBySlideId,
  durationInFrames
}: Props) {
  const slides = course.chapterContentSlide || [];

  const getChapterDuration = (chapterId: string): number => {
    if (!durationBySlideId) return 30;
    return (
      slides
        .filter((s) => s.chapterId === chapterId)
        .reduce(
          (sum, slide) => sum + (durationBySlideId[slide.slideId] || FPS * 6),
          0
        ) || 30
    );
  };

  const formatDuration = (frames: number): string => {
    const seconds = Math.round(frames / FPS);
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return minutes > 0 ? `${minutes}m ${remaining}s` : `${seconds}s`;
  };

  return (
    <div className="max-w-6xl w-full mt-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-bold text-3xl">Course Chapters</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {course.courseLayout?.chapters?.length || 0} chapters • Watch
            chapter previews
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {course.courseLayout?.chapters?.map((chapter, index) => {
          const chapterSlides = slides.filter(
            (s) => s.chapterId === chapter.chapterId
          );
          const chapterDuration = getChapterDuration(chapter.chapterId);
          const hasContent = chapterSlides.length > 0;

          return (
            <div
              key={chapter.chapterId}
              className="border rounded-2xl shadow-sm bg-white overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="p-6">
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg flex-shrink-0">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-xl mb-1">
                      {chapter.chapterTitle}
                    </h3>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Play className="w-4 h-4" />
                        <span>{chapterSlides.length} slides</span>
                      </div>
                      {hasContent && durationBySlideId && (
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          <span>{formatDuration(chapterDuration)}</span>
                        </div>
                      )}
                      {!hasContent && (
                        <span className="text-amber-600 font-medium">
                          Content not generated
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
                      Topics Covered
                    </h4>
                    <Card className="border-2">
                      <CardContent className="pt-4">
                        <div className="space-y-2">
                          {chapter.subContent?.map((content, ci) => (
                            <div key={ci} className="flex items-start gap-2">
                              <Dot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                              <p className="text-sm text-gray-700 leading-relaxed">
                                {content}
                              </p>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
                      Chapter Preview
                    </h4>
                    {durationBySlideId && chapterSlides.length > 0 ? (
                      <div className="border-2 border-gray-200 rounded-xl overflow-hidden bg-gray-50 shadow-sm">
                        <Player
                          component={CourseComposition}
                          durationInFrames={chapterDuration}
                          compositionWidth={1280}
                          compositionHeight={720}
                          fps={FPS}
                          style={{ width: "100%", aspectRatio: "16/9" }}
                          controls
                          inputProps={{
                            slides: chapterSlides,
                            durationBySlideId
                          }}
                        />
                      </div>
                    ) : (
                      <div className="w-full aspect-video bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl border-2 border-dashed border-gray-300 flex flex-col items-center justify-center">
                        <Play className="w-12 h-12 text-gray-400 mb-2" />
                        <p className="text-sm text-gray-500 font-medium">
                          Video preview not available
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                          Generate content to see preview
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {(!course.courseLayout?.chapters ||
        course.courseLayout.chapters.length === 0) && (
        <div className="border-2 border-dashed rounded-2xl p-12 text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Play className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            No Chapters Available
          </h3>
          <p className="text-sm text-gray-500">
            Course content will appear here once generated
          </p>
        </div>
      )}
    </div>
  );
}
