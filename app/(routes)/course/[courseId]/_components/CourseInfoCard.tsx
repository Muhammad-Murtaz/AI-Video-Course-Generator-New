import { Course } from "@/type/CourseType";
import { Player } from "@remotion/player";
import { Sparkles, BarChart2Icon, BookOpen } from "lucide-react";
import ChapterVideo from "./ChapterVideo";
import { useMemo } from "react";

interface Props {
  course?: Course;
  durationBySlideId: Record<string, number> | null;
}

const FPS = 30;

function CourseInfoCard({ course, durationBySlideId }: Props) {
  // Use courseIntroSlides if available, otherwise fallback to chapter slides
  const slides =
    course?.courseIntroSlides && course.courseIntroSlides.length > 0
      ? course.courseIntroSlides
      : (course?.chapterContentSlide ?? []);

  const durationInFrames = useMemo(() => {
    if (!durationBySlideId || slides.length === 0) return 30;
    return slides.reduce((sum, slide) => {
      return sum + (durationBySlideId[slide.slideId] || FPS * 6);
    }, 0);
  }, [durationBySlideId, slides]);

  const isIntroVideo =
    course?.courseIntroSlides && course.courseIntroSlides.length > 0;

  return (
    <div className="w-full max-w-7xl mx-auto">
      <div className="bg-gradient-to-br from-slate-950 via-slate-800 to-emerald-950 rounded-2xl p-8 md:p-12 text-white border border-gray-400/40">
        <h2 className="inline-flex items-center gap-2 px-2 py-1 border border-gray-400/40 rounded-2xl text-sm">
          <Sparkles className="w-4 h-4" />
          {isIntroVideo ? "Course Introduction" : "Course Preview"}
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-6">
          <div>
            <h2 className="text-4xl md:text-5xl font-bold">
              {course?.courseLayout?.courseName}
            </h2>
            <p className="text-lg text-gray-300 mt-3">
              {course?.courseLayout?.courseDescription}
            </p>

            <div className="flex gap-4 mt-5 flex-wrap">
              <h2 className="inline-flex items-center gap-2 px-3 py-2 border border-gray-400/40 rounded text-white">
                <BarChart2Icon className="w-5 h-5 text-sky-400" />
                {course?.courseLayout?.level}
              </h2>
              <h2 className="inline-flex items-center gap-2 px-3 py-2 border border-gray-400/40 rounded text-white">
                <BookOpen className="w-5 h-5 text-emerald-400" />
                {course?.courseLayout?.totalChapters} Chapters
              </h2>
            </div>

            {isIntroVideo && (
              <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <p className="text-sm text-blue-300">
                  🎬 Watch the introduction to get an overview of what you'll
                  learn in this course
                </p>
              </div>
            )}
          </div>

          <div className="rounded-xl overflow-hidden border border-white/10">
            {durationBySlideId && slides.length > 0 ? (
              <Player
                component={ChapterVideo}
                durationInFrames={durationInFrames}
                compositionWidth={1920}
                compositionHeight={1080}
                fps={30}
                inputProps={{
                  slides: slides,
                  durationBySlideId: durationBySlideId
                }}
                controls
                loop
                style={{
                  width: "100%",
                  aspectRatio: "16/9"
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full bg-slate-900 aspect-video">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                  <p className="text-white">
                    {isIntroVideo
                      ? "Generating introduction..."
                      : "Loading video..."}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CourseInfoCard;
