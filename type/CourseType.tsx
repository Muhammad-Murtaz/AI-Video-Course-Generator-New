export type GenStatus = "idle" | "generating" | "done" | "error";

export interface CaptionChunk {
  text: string;
  start?: number;
  end?: number;
}

export interface Caption {
  chunks?: CaptionChunk[];
  [key: string]: any;
}

export interface ChapterContentSlide {
  id?: number;
  courseId: string;
  chapterId: string;
  slideId: string;
  slideIndex: number;
  audioFileName: string;
  narration: { fullText: string };
  html: string;
  revealData: any;
  audioFileUrl?: string;
  caption?: Caption;
}

export interface CourseIntroSlide {
  id?: number;
  courseId: string;
  slideId: string;
  slideIndex: number;
  audioFileName: string;
  narration: { fullText: string };
  html: string;
  revealData: any;
  audioFileUrl?: string;
  caption?: Caption;
}

export interface Chapter {
  chapterId: string;
  chapterTitle: string;
  subContent?: string[];
}

export interface CourseLayout {
  courseName: string;
  courseDescription?: string;
  courseId?: string;
  level?: string;
  totalChapters?: number;
  chapters: Chapter[];
}

export interface Course {
  id?: number;
  courseId: string;
  courseName?: string;
  userId?: string;
  userInput?: string;
  type?: string;
  courseLayout: CourseLayout;
  createdAt?: string;
  courseIntroSlides?: CourseIntroSlide[];
  chapterContentSlide?: ChapterContentSlide[];
}