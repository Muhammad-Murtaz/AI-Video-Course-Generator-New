"use client";
import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import { toast } from "sonner";
import { getAudioData } from "@remotion/media-utils";
import CourseInfoCard from "./_components/CourseInfoCard";
import CourseChapters from "./_components/CourseChapters";
import { Course } from "@/type/CourseType";

const FPS = 30;

export default function CoursePreview() {
  const { courseId } = useParams();
  const [courseDetail, setCourseDetail] = useState<Course | null>(null);
  const [introDurationBySlideId, setIntroDurationBySlideId] = useState<Record<
    string,
    number
  > | null>(null);
  const [chapterDurationBySlideId, setChapterDurationBySlideId] =
    useState<Record<string, number> | null>(null);

  useEffect(() => {
    setCourseDetail(null);
    setIntroDurationBySlideId(null);
    setChapterDurationBySlideId(null);
    getCourseDetail();
  }, [courseId]);

  useEffect(() => {
    if (!courseDetail) return;
    const run = async () => {
      const [introDurations, chapterDurations] = await Promise.all([
        computeDurations(courseDetail.courseIntroSlides || []),
        computeDurations(courseDetail.chapterContentSlide || [])
      ]);
      if (introDurations) setIntroDurationBySlideId(introDurations);
      if (chapterDurations) setChapterDurationBySlideId(chapterDurations);
    };
    run();
  }, [courseDetail]);

  const computeDurations = async (
    slides: { slideId: string; audioFileUrl?: string | null }[]
  ) => {
    if (!slides.length) return null;
    const entries = await Promise.all(
      slides.map(async (slide) => {
        const audioData = await getAudioData(slide.audioFileUrl ?? "");
        const frames = Math.max(
          1,
          Math.round(audioData.durationInSeconds * FPS)
        );
        return [slide.slideId, frames] as [string, number];
      })
    );
    return Object.fromEntries(entries);
  };

  const getCourseDetail = async () => {
    const t = toast.loading("Fetching course...");
    try {
      const result = await axios.get(`/api/course?course_id=${courseId}`);
      const course: Course = result.data;
      console.log(JSON.stringify(course));
      setCourseDetail(course);
      toast.success("Course loaded!", { id: t });
      await generateMissingContent(course);
    } catch {
      toast.error("Failed to fetch course!", { id: t });
    }
  };

  const generateMissingContent = async (course: Course) => {
    const allChapters = course.courseLayout?.chapters || [];
    const generatedChapterIds = new Set(
      (course.chapterContentSlide || []).map((s) => s.chapterId)
    );
    const missingChapters = allChapters.filter(
      (ch) => !generatedChapterIds.has(ch.chapterId)
    );
    const needsIntro = !course.courseIntroSlides?.length;

    if (!needsIntro && missingChapters.length === 0) return;

    const tasks: Promise<void>[] = [];

    if (needsIntro) {
      tasks.push(
        (async () => {
          const t = toast.loading("Generating course intro...");
          try {
            await axios.post("/api/generate-course-intro", {
              courseId,
              courseLayout: course.courseLayout
            });
            toast.success("Course intro generated!", { id: t });
          } catch {
            toast.error("Failed to generate intro", { id: t });
          }
        })()
      );
    }

    if (missingChapters.length > 0) {
      tasks.push(
        (async () => {
          for (const chapter of missingChapters) {
            const t = toast.loading(`Generating "${chapter.chapterTitle}"...`);
            try {
              await axios.post("/api/generate-video-content", {
                chapter,
                courseId
              });
              toast.success(`"${chapter.chapterTitle}" generated!`, { id: t });
            } catch {
              toast.error(`Failed for "${chapter.chapterTitle}"`, { id: t });
            }
          }
        })()
      );
    }

    await Promise.all(tasks);
    getCourseDetail();
  };

  const introDurationInFrames = useMemo(() => {
    if (!introDurationBySlideId || !courseDetail?.courseIntroSlides) return 30;
    return courseDetail.courseIntroSlides.reduce(
      (sum, slide) => sum + (introDurationBySlideId[slide.slideId] || FPS * 6),
      0
    );
  }, [introDurationBySlideId, courseDetail]);

  const chapterDurationInFrames = useMemo(() => {
    if (!chapterDurationBySlideId || !courseDetail?.chapterContentSlide)
      return 30;
    return courseDetail.chapterContentSlide.reduce(
      (sum, slide) =>
        sum + (chapterDurationBySlideId[slide.slideId] || FPS * 6),
      0
    );
  }, [chapterDurationBySlideId, courseDetail]);

  if (!courseDetail) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-500 text-lg">Loading course...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center px-4 py-6">
      <CourseInfoCard
        course={courseDetail}
        durationBySlideId={introDurationBySlideId}
        durationInFrames={introDurationInFrames}
      />
      <CourseChapters
        course={courseDetail}
        durationBySlideId={chapterDurationBySlideId}
        durationInFrames={chapterDurationInFrames}
      />
    </div>
  );
}
