import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0c6b67",
          color: "#ffffff",
          fontFamily: "Georgia, 'Times New Roman', serif",
        }}
      >
        <span
          style={{
            fontSize: 34,
            fontWeight: 900,
            letterSpacing: "-0.08em",
            lineHeight: 1,
          }}
        >
          V$
        </span>
      </div>
    ),
    size,
  );
}