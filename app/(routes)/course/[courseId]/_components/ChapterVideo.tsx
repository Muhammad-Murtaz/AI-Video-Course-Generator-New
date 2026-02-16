"use client";
import { ChapterContentSlide, CourseIntroSlide } from "@/type/CourseType";
import {
  useCurrentFrame,
  useVideoConfig,
  Audio,
  AbsoluteFill,
  Sequence
} from "remotion";

type AnySlide = ChapterContentSlide | CourseIntroSlide;

interface Props {
  slides: AnySlide[];
  durationBySlideId: Record<string, number>;
}

const getSlideAtFrame = (
  frame: number,
  slides: AnySlide[],
  durationBySlideId: Record<string, number>
) => {
  let cumulative = 0;
  for (const slide of slides) {
    const dur = durationBySlideId[slide.slideId] || 180;
    if (frame < cumulative + dur) {
      return {
        slide,
        localFrame: frame - cumulative,
        duration: dur,
        startFrame: cumulative
      };
    }
    cumulative += dur;
  }
  const last = slides[slides.length - 1];
  const lastDur = durationBySlideId[last?.slideId] || 180;
  return {
    slide: last,
    localFrame: lastDur - 1,
    duration: lastDur,
    startFrame: cumulative - lastDur
  };
};

export default function CourseComposition({
  slides,
  durationBySlideId
}: Props) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!slides?.length) {
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

  const { slide, localFrame, duration, startFrame } = getSlideAtFrame(
    frame,
    slides,
    durationBySlideId
  );
  const currentTime = localFrame / fps;
  const currentCaption =
    slide?.caption?.chunks?.find(
      (chunk) =>
        chunk.start !== undefined &&
        chunk.end !== undefined &&
        currentTime >= chunk.start &&
        currentTime <= chunk.end
    )?.text || "";

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
        {slide?.audioFileUrl && (
          <Sequence from={startFrame} durationInFrames={duration}>
            <Audio src={slide.audioFileUrl} />
          </Sequence>
        )}
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
