import { useEffect, useState } from "react";
import { api, type CameraStatus } from "../lib/api";
import { useTopic } from "../lib/ws";

// The vision service serves the MJPEG preview on its own port (config
// preview_port, default 8090) on the Pi, streamed only when enabled.
const STREAM_URL = `${location.protocol}//${location.hostname}:8090/stream`;

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

export default function Camera() {
  const live = useTopic<CameraStatus>("camera");
  const [seed, setSeed] = useState<CameraStatus | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.cameraStatus().then(setSeed).catch(() => setSeed({ running: false }));
  }, []);

  const cam = live ?? seed;
  const face = cam?.face ?? null;
  const previewOn = Boolean(cam?.preview);
  const trackingOn = cam?.tracking !== false;   // default on until we hear otherwise

  const togglePreview = async () => {
    setBusy(true);
    try {
      await api.updateSettings([{ key: "camera.preview_enabled", value: !previewOn }]);
    } finally {
      setBusy(false);
    }
  };

  const toggleTracking = async () => {
    setBusy(true);
    try {
      await api.updateSettings([{ key: "camera.tracking_enabled", value: !trackingOn }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-lg font-semibold">Camera</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTracking}
            disabled={busy || !cam?.running}
            className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
              trackingOn ? "bg-led-working text-neutral-950" : "bg-neutral-800 text-neutral-300"
            }`}
          >
            Tracking: {trackingOn ? "on" : "off"}
          </button>
          <button
            onClick={togglePreview}
            disabled={busy || !cam?.running}
            className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
              previewOn ? "bg-led-error/90 text-white" : "bg-led-idle text-white"
            }`}
          >
            {previewOn ? "Stop live video" : "Start live video"}
          </button>
          <button
            onClick={() => api.cameraCenter()}
            className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm hover:bg-neutral-700"
          >
            Center
          </button>
        </div>
      </div>
      <p className="text-sm text-neutral-500 mb-5">
        Live face tracking from the vision service. Video is off by default (privacy)
        and streams only while enabled.
      </p>

      {!cam?.running ? (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-6 text-sm text-neutral-400">
          Vision service offline — no camera status is being published.
          <div className="mt-1 text-xs text-neutral-600">
            Start it on the Pi: <code>systemctl start deskbot-vision</code>
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <Stat label="FPS" value={cam.fps?.toFixed(1) ?? "—"} />
            <Stat label="Detect" value={cam.detect_ms != null ? `${cam.detect_ms} ms` : "—"} />
            <Stat
              label="Presence"
              value={cam.present ? "present" : "away"}
              tone={cam.present ? "text-led-working" : "text-neutral-500"}
            />
            <Stat label="Faces" value={String(cam.faces ?? 0)} />
          </div>

          <div className="relative w-full max-w-lg aspect-[4/3] rounded-lg border border-neutral-700 bg-neutral-950 overflow-hidden">
            {previewOn ? (
              // MJPEG stream renders live inside an <img>
              <img
                src={STREAM_URL}
                alt="camera preview"
                className="absolute inset-0 h-full w-full object-cover"
                onError={(e) => (e.currentTarget.style.opacity = "0.15")}
              />
            ) : (
              <>
                {/* privacy mode: abstract face-position plot, no actual video */}
                <div className="absolute inset-y-0 left-1/2 w-px bg-neutral-800" />
                <div className="absolute inset-x-0 top-1/2 h-px bg-neutral-800" />
                {face ? (
                  <div
                    className="absolute h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-md border-2 border-led-working transition-all duration-100"
                    style={{ left: `${face.cx * 100}%`, top: `${face.cy * 100}%` }}
                  >
                    <span className="absolute -top-5 left-0 text-[10px] text-led-working">
                      {(face.score * 100).toFixed(0)}%
                    </span>
                  </div>
                ) : (
                  <div className="absolute inset-0 grid place-items-center text-sm text-neutral-600">
                    no face
                  </div>
                )}
              </>
            )}
            {busy && (
              <div className="absolute bottom-2 right-2 text-[10px] text-neutral-400">
                applying…
              </div>
            )}
          </div>

          {face && (
            <div className="mt-3 text-sm text-neutral-400 tabular-nums">
              error&nbsp; x&nbsp;<span className="text-neutral-200">{face.err_x >= 0 ? "+" : ""}{face.err_x.toFixed(2)}</span>
              &nbsp;&nbsp; y&nbsp;<span className="text-neutral-200">{face.err_y >= 0 ? "+" : ""}{face.err_y.toFixed(2)}</span>
              <span className="text-neutral-600"> — this drives the servos next</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
