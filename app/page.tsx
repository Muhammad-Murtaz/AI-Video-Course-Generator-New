import CourseList from "./_components/CourseList";
import Header from "./_components/Header";
import Hero from "./_components/Hero";

export default function HomePage() {
  return (
    <div>
      <Header />
      {/* Hero */}

      <Hero />
      <CourseList />


        {/* Purple circle - bottom left */}
        <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] bg-purple-400/20 blur-[120px] rounded-full" />

        {/* Pink circle - top left */}
        <div className="absolute top-20 left-1/3 h-[500px] w-[500px] bg-pink-400/20 blur-[120px] rounded-full" />

        {/* Blue circle - bottom center */}
        <div className="absolute bottom-[200px] left-1/3 h-[500px] w-[500px] bg-blue-400/10 blur-[100px] rounded-full" />

        {/* Sky blue circle - top center */}
        <div className="absolute top-[200px] left-1/2 h-[500px] w-[500px] bg-sky-400/20 blur-[120px] rounded-full" />
   
    </div>
  );
}
