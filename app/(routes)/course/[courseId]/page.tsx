"use client";
import React, { ReactNode, useEffect, useState } from "react";
import CourseInfoCard from "./_components/CourseInfoCard";
import { useParams } from "next/navigation";
import { Course } from "@/type/CourseType";
import { toast } from "sonner";
import axios from "axios";
import CourseChapters from "./_components/CourseChapters";
import { getAudioData } from "@remotion/media-utils";

type CoursePreviewProps = {
  children?: ReactNode;
};

const FPS = 30;

function CoursePreview(props: CoursePreviewProps) {
  const { courseId } = useParams();
  const [courseDetails, setCourseDetails] = useState<Course | undefined>(
    undefined
  );
  const [durationBySlideId, setDurationBySlideId] = useState<Record<
    string,
    number
  > | null>(null);

  // Load course details when component mounts
  useEffect(() => {
    getUserCourseDeatils();
  }, [courseId]);

  // Generate course intro after course details are loaded
  useEffect(() => {
    if (courseDetails && courseDetails.courseIntroSlides?.length === 0) {
      console.log("Course loaded, generating intro...");
      generateCourseIntro();
    }
  }, [courseDetails]);

  const generateCourseIntro = async () => {
    console.log("Generating course introduction...");
    const t = toast.loading("Generating course introduction...");
    try {
      const result = await axios.post("/api/generate-course-intro", {
        courseId: courseDetails?.courseId,
        courseLayout: courseDetails?.courseLayout
      });

      toast.success("Introduction generated!", { id: t });
      await getUserCourseDeatils(); // Refresh
    } catch (e) {
      toast.error("Failed to generate introduction", { id: t });
    }
  };

  // Calculate durations when course details are loaded
  useEffect(() => {
    const calculateDurations = async () => {
      const allSlides = [
        ...(courseDetails?.courseIntroSlides || []),
        ...(courseDetails?.chapterContentSlide || [])
      ];

      if (allSlides.length === 0) {
        return;
      }

      try {
        const entries = await Promise.all(
          allSlides.map(async (slide) => {
            // Skip slides without slide_id or audio_file_url
            if (!slide.slideId || !slide.audioFileUrl) {
              console.warn(`Skipping slide without ID or audio URL:`, slide);
              return [slide.slideId || "unknown", FPS * 6] as [string, number];
            }

            try {
              const audioData = await getAudioData(slide.audioFileUrl);
              console.log(`✅ Audio loaded for ${slide.slideId}:`, {
                duration: audioData.durationInSeconds,
                url: slide.audioFileUrl
              });

              const audioSeconds = audioData.durationInSeconds;
              const frames = Math.max(1, Math.round(audioSeconds * FPS));
              return [slide.slideId, frames] as [string, number];
            } catch (error) {
              console.warn(
                `Could not load audio for slide ${slide.slideId}, using default duration. Error:`,
                error
              );
              return [slide.slideId, FPS * 6] as [string, number]; // Default 6 seconds
            }
          })
        );

        const durationMap = Object.fromEntries(entries);
        setDurationBySlideId(durationMap);
      } catch (error) {
        console.error("Error calculating durations:", error);
        // Set default durations for all slides as fallback
        const defaultDurations = Object.fromEntries(
          allSlides
            .filter((slide) => slide.slideId)
            .map((slide) => [slide.slideId, FPS * 6])
        );
        setDurationBySlideId(defaultDurations);
      }
    };

    calculateDurations();
  }, [courseDetails]);

  const getUserCourseDeatils = async () => {
    const loadingToast = toast.loading("Loading course details...");
    try {
      const result = await axios.get(`/api/course?courseId=${courseId}`);
      console.log("Course Details:", result.data.course);
      setCourseDetails(result.data.course);
      console.log(
        "Has chapters:",
        result.data.course.chapterContentSlide?.length > 0
      );

      toast.success("Course detail fetched successfully!", {
        id: loadingToast
      });

      const totalChapters =
        result.data.course.courseLayout.chapters?.length || 0;
      const existingSlides =
        result.data.course.chapterContentSlide?.length || 0;

      if (existingSlides < totalChapters) {
        console.log(
          `Generating remaining slides: ${existingSlides}/${totalChapters}`
        );
        await generateVideoContent(result.data.course);
      }
    } catch (error) {
      toast.error("Failed to fetch course!", { id: loadingToast });
    }
  };

  // page.tsx
  const generateVideoContent = async (course: Course) => {
    const chapters = course.courseLayout.chapters || [];

    for (let i = 0; i < chapters.length; i++) {
      const existingSlide = course.chapterContentSlide?.find(
        (slide) => slide.chapterId === chapters[i].chapterId
      );

      if (existingSlide) {
        console.log(`Skipping chapter ${i + 1} - already exists`);
        continue;
      }

      const t = toast.loading(`Generating: ${chapters[i].chapterTitle}`);
      try {
        const result = await axios.post("/api/generate-video-content", {
          chapter: chapters[i],
          courseId: course.courseId
        });

        if (result.data.skipped) {
          toast.info(`Chapter ${i + 1} already exists`, { id: t });
        } else {
          toast.success(`Chapter ${i + 1} complete!`, { id: t });
        }
      } catch (e) {
        toast.error(`Failed chapter ${i + 1}`, { id: t });
      }
    }
  };

  if (!courseDetails) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-500 text-lg">Loading course...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center px-4 py-6">
      <CourseInfoCard
        course={courseDetails}
        durationBySlideId={durationBySlideId}
      />
      <CourseChapters
        course={courseDetails}
        durationBySlideId={durationBySlideId}
      />
    </div>
  );
}

export default CoursePreview;
