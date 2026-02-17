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
      {/* Audio track for this slide */}
      {slide?.audioFileUrl && (
        <Sequence from={startFrame} durationInFrames={duration}>
          <Audio src={slide.audioFileUrl} />
        </Sequence>
      )}

      {/*
        FIX: The LLM generates HTML with a root div already set to
        width:1280px; height:720px (exactly the Remotion canvas size).
        The old code wrapped it in a 900px-max div, squeezing the 1280px
        element and pushing content into a corner.

        Solution: dangerouslySetInnerHTML goes directly onto AbsoluteFill's
        inner div at full 1280×720 with no extra wrapper or max-width.
        We use a CSS scale() transform so the HTML renders at native
        1280×720 and then scales down to fit the preview Player width,
        keeping everything perfectly centered.
      */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1280,
          height: 720,
          transformOrigin: "top left",
          transform: "scale(var(--remotion-scale, 1))",
          // Dark fallback so white text is always readable if the LLM HTML
          // background hasn't loaded yet or doesn't cover the full canvas.
          background:
            "linear-gradient(135deg, #0f0f1a 0%, #0a0a2e 50%, #0d1117 100%)"
        }}
        dangerouslySetInnerHTML={{ __html: slide?.html || "" }}
      />

      {/* Caption bar — always sits above the HTML layer at the bottom */}
      {currentCaption ? (
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            width: "100%",
            background: "rgba(0,0,0,0.72)",
            padding: "14px 32px",
            minHeight: 52,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10
          }}
        >
          <p
            style={{
              color: "#fff",
              fontSize: 22,
              textAlign: "center",
              fontFamily: "sans-serif",
              lineHeight: 1.4,
              textShadow: "0 1px 4px rgba(0,0,0,0.8)"
            }}
          >
            {currentCaption}
          </p>
        </div>
      ) : null}
    </AbsoluteFill>
  );
}
