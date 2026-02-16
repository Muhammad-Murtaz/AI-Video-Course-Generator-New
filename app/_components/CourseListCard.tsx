"use client";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Play, Layers, Calendar } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Course } from "@/type/CourseType";

interface Props {
  course: Course;
}

export default function CourseListCard({ course }: Props) {
  const name = course.courseName ?? course.courseLayout?.courseName ?? "Untitled";
  const level = course.courseLayout?.level;
  const chapters = course.courseLayout?.totalChapters ?? 0;
  const createdAt = course.createdAt ? new Date(course.createdAt) : null;

  return (
    <Card className="group hover:shadow-md transition-shadow duration-200">
      {/* Top color strip */}
      <div className="h-1.5 w-full bg-gradient-to-r from-primary/70 to-primary rounded-t-xl" />

      <CardContent className="pt-4 pb-5 px-5">
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3 className="font-semibold text-sm leading-snug line-clamp-2">{name}</h3>
          {level && (
            <span className="text-xs px-2 py-0.5 border rounded-full border-primary/40 text-primary bg-primary/5 whitespace-nowrap flex-shrink-0">
              {level}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs text-muted-foreground mb-4 flex-wrap">
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3" />
            {chapters} chapters
          </span>
          {createdAt && (
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {formatDistanceToNow(createdAt, { addSuffix: true })}
            </span>
          )}
        </div>

        <Link href={`/course/${course.courseId}`}>
          <Button size="sm" className="w-full group-hover:bg-primary/90 transition-colors">
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Watch Now
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}