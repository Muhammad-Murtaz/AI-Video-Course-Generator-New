"use client";
import Link from "next/link";
import moment from "moment";
import { Play, Layers, Calendar, Dot } from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Course } from "@/type/CourseType";

interface Props {
  course: Course;
}

export default function CourseListCard({ course }: Props) {
  return (
    <Card className="w-full bg-white">
      <CardHeader className="bg-white p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium">{course.courseName || course.courseLayout?.courseName}</h2>
          <h2 className="text-sm px-2 py-1 border rounded-2xl border-primary text-primary bg-primary/10">
            {course.courseLayout?.level}
          </h2>
        </div>

        <div className="flex items-center gap-3 mt-2">
          <h2 className="flex items-center gap-1 text-xs text-slate-600 bg-slate-100 border border-slate-300 px-2 py-1 rounded">
            <Layers className="w-3 h-3" />
            {course.courseLayout?.totalChapters} Chapters
          </h2>
          <h2 className="flex items-center gap-1 text-xs text-slate-600 bg-slate-100 border border-slate-300 px-2 py-1 rounded">
            <Calendar className="w-3 h-3" />
            {moment(course.createdAt).format("MM/DD/YYYY")}
            <Dot className="w-4 h-4" />
            {moment(course.createdAt).fromNow()}
          </h2>
        </div>
      </CardHeader>

      <CardContent className="bg-white">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Keep learning</p>
          <Link href={`/course/${course.courseId}`}>
            <Button size="sm">
              <Play className="w-4 h-4 mr-1" /> Watch Now
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}