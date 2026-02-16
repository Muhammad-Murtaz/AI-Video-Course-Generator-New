import CourseList from "./_components/CourseList";
import Header from "./_components/Header";
import Hero from "./_components/Hero";

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <Header />
      <Hero />
      <CourseList />

      {/* Ambient background blobs — need relative parent above to work */}
      <div
        className="pointer-events-none fixed inset-0 -z-10"
        aria-hidden="true"
      >
        <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] bg-purple-400/20 blur-[120px] rounded-full" />
        <div className="absolute top-20 left-1/3 h-[500px] w-[500px] bg-pink-400/20 blur-[120px] rounded-full" />
        <div className="absolute bottom-[200px] left-1/3 h-[500px] w-[500px] bg-blue-400/10 blur-[100px] rounded-full" />
        <div className="absolute top-[200px] left-1/2 h-[500px] w-[500px] bg-sky-400/20 blur-[120px] rounded-full" />
      </div>
    </div>
  );
}
