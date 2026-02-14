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
    if (user) getCourseList();
  }, [user]);

  const getCourseList = async () => {
    try {
      const result = await axios.get("/api/course");
      console.log("Course :", result.data);
      const transformedData: Course[] = result.data.map((course: any) => ({
        id: course.id,
        courseId: course.course_id,
        courseName: course.course_name,
        userId: course.user_id,
        userInput: course.user_input,
        type: course.type,
        courseLayout: course.course_layout,
        createdAt: course.created_at
      }));

      setCourseList(transformedData);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="max-w-6xl w-full mt-10 px-4">
      {/* {!user && (
        <>
          <h2 className="font-bold text-xl">Popular Courses</h2>
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 mt-3">
            {HERO_COURSES.map((c, i) => (
              <CourseListCard key={i} course={c as any} />
            ))}
          </div>
        </>
      )} */}

      {user && courseList.length > 0 && (
        <>
          <h2 className="font-bold text-xl">My Courses</h2>
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-3 mt-3 bg-white">
            {courseList.map((c, i) => (
              <CourseListCard key={i} course={c} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
