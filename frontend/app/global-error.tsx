"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Verda] global error", error);
  }, [error]);

  // Renders OUTSIDE the root layout, so it must include its own <html>/<body>.
  // Kept stylesheet-free so even a render-time CSS bug can't suppress it.
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          background: "#faf6ec",
          color: "#0a1429",
          fontFamily:
            "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          display: "grid",
          placeItems: "center",
          padding: "32px 16px",
        }}
      >
        <div style={{ maxWidth: 540, textAlign: "center" }}>
          <div
            aria-hidden="true"
            style={{
              width: 56,
              height: 56,
              margin: "0 auto 16px",
              borderRadius: 14,
              background: "#0a1429",
              color: "#faf6ec",
              display: "grid",
              placeItems: "center",
              fontWeight: 700,
              fontSize: 22,
            }}
          >
            V
          </div>
          <p
            style={{
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(10,20,41,0.55)",
              margin: 0,
            }}
          >
            Fatal error
          </p>
          <h1
            style={{
              fontFamily: "'Source Serif 4', Georgia, serif",
              fontSize: 28,
              fontWeight: 700,
              margin: "8px 0 12px",
              letterSpacing: "-0.01em",
            }}
          >
            Verda could not render this page.
          </h1>
          <p style={{ fontSize: 14, color: "rgba(10,20,41,0.65)", margin: 0 }}>
            The application crashed before the layout could load. Try reloading
            once. If it persists, the operator should check the dev server
            console.
          </p>
          {error.message ? (
            <pre
              style={{
                marginTop: 20,
                padding: "10px 12px",
                background: "rgba(184,92,32,0.08)",
                border: "1px solid rgba(184,92,32,0.35)",
                borderRadius: 10,
                fontSize: 11,
                color: "#b85c20",
                textAlign: "left",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                maxHeight: 160,
                overflow: "auto",
              }}
            >
              {error.message}
              {error.digest ? `\n\ndigest: ${error.digest}` : ""}
            </pre>
          ) : null}
          <button
            onClick={() => reset()}
            style={{
              marginTop: 24,
              padding: "10px 18px",
              borderRadius: 10,
              background: "#0a1429",
              color: "#faf6ec",
              border: 0,
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
