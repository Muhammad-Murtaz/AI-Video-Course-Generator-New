"use client";
import { ChapterContentSlide } from "@/type/CourseType";
import {
  useCurrentFrame,
  useVideoConfig,
  Audio,
  AbsoluteFill,
  Sequence
} from "remotion";

interface Props {
  slides: ChapterContentSlide[];
  durationBySlideId: Record<string, number> | null;
}

const DEFAULT_SLIDE_DURATION = 180; // 6 seconds at 30fps

// Single slide component
function SlideContent({
  slide,
  duration
}: {
  slide: ChapterContentSlide;
  duration: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const captionChunks = slide?.caption?.chunks || [];
  const currentTime = frame / fps;
  let currentCaption = "";

  for (const chunk of captionChunks) {
    if (chunk.start !== undefined && chunk.end !== undefined) {
      if (currentTime >= chunk.start && currentTime <= chunk.end) {
        currentCaption = chunk.text || "";
        break;
      }
    }
  }

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%)",
          overflow: "hidden"
        }}
      >
        {/* Audio */}
        {slide?.audioFileUrl && <Audio src={slide.audioFileUrl} />}

        {/* Slide HTML */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "85%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "40px"
          }}
        >
          <div
            dangerouslySetInnerHTML={{ __html: slide?.html || "" }}
            style={{ color: "#fff", width: "100%", maxWidth: "900px" }}
          />
        </div>

        {/* Caption bar */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            width: "100%",
            background: "rgba(0,0,0,0.6)",
            padding: "12px 24px",
            minHeight: "50px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}
        >
          <p
            style={{
              color: "#fff",
              fontSize: 20,
              textAlign: "center",
              fontFamily: "sans-serif"
            }}
          >
            {currentCaption}
          </p>
        </div>
      </div>
    </AbsoluteFill>
  );
}

export default function CourseComposition({
  slides,
  durationBySlideId
}: Props) {
  if (!slides || slides.length === 0) {
    return (
      <AbsoluteFill>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "100%",
            height: "100%",
            background: "#111"
          }}
        >
          <p style={{ color: "#fff", fontSize: 28 }}>No slides available</p>
        </div>
      </AbsoluteFill>
    );
  }

  // Calculate cumulative start times for each slide
  let cumulativeFrame = 0;
  const slideSequences = slides.map((slide) => {
    const duration =
      durationBySlideId?.[slide.slideId] || DEFAULT_SLIDE_DURATION;
    const startFrame = cumulativeFrame;
    cumulativeFrame += duration;

    return {
      slide,
      from: startFrame,
      durationInFrames: duration
    };
  });

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {slideSequences.map((seq, index) => (
        <Sequence
          key={seq.slide.slideId || index}
          from={seq.from}
          durationInFrames={seq.durationInFrames}
        >
          <SlideContent slide={seq.slide} duration={seq.durationInFrames} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
}
