"use client";
import { useEffect, useState } from "react";
import axios from "axios";
import { useUser } from "@clerk/nextjs";
import CourseListCard from "./CourseListCard";
import { Course } from "@/type/CourseType";

export default function CourseList() {
  const { user } = useUser();
  const [courseList, setCourseList] = useState<Course[]>([]);

  useEffect(() => {
    if (user) fetchCourses();
  }, [user]);

  const fetchCourses = async () => {
    try {
      const { data } = await axios.get("/api/course");
      // Backend returns { courses: [...] }
      const raw: any[] = data.courses ?? data;

      const courses: Course[] = raw.map((c) => ({
        id: c.id,
        courseId: c.course_id ?? c.courseId,
        courseName: c.course_name ?? c.courseName,
        userId: c.user_id ?? c.userId,
        userInput: c.user_input ?? c.userInput,
        type: c.type,
        courseLayout: c.course_layout ?? c.courseLayout,
        createdAt: c.created_at ?? c.createdAt,
      }));

      setCourseList(courses);
    } catch {
      // silently fail — user sees empty state
    }
  };

  if (!user || courseList.length === 0) return null;

  return (
    <div className="max-w-6xl w-full mt-10 px-4">
      <h2 className="font-bold text-xl mb-3">My Courses</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {courseList.map((c) => (
          <CourseListCard key={c.courseId} course={c} />
        ))}
      </div>
    </div>
  );
}