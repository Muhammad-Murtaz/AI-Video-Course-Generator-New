export type Course = {
  id?: number;
  courseId: string;
  courseName: string;
  userId?: string;
  userInput?: string;
  type?: string;
  courseLayout: CourseLayout;
  createdAt?: string;
  courseIntroSlides?: ChapterContentSlide[];
  chapterContentSlide?: ChapterContentSlide[];
};

export type CourseLayout = {
  courseName: string;
  courseDescription: string;
  courseId: string;
  level: string;
  totalChapters: number;
  chapters: Chapter[];
};

export type Chapter = {
  chapterId: string;
  chapterTitle: string;
  subContent: string[];
};

export interface ChapterContentSlide {
  id: number;
  courseId: string;
  chapterId: string;
  slideId: string;
  slideIndex: number;
  audioFileName: string;
  audioFileUrl: string;
  narration: { fullText: string };
  html: string;
  revealData: any;
  caption: any;
}
