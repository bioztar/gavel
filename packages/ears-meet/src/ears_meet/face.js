// Karen's camera tile: one still image, published as a real video track.
//
// Why a canvas and not Chromium's own fake camera: the only flag pair that feeds a file to
// the camera (`--use-fake-device-for-media-stream` plus `--use-file-for-fake-video-capture`)
// also replaces Chromium's audio manager. Measured 2026-09-22 under Xvfb: with those flags
// `enumerateDevices()` returns only "Fake Default Audio Input" / "Fake Audio Input 1" / "Fake
// Audio Input 2", and the file flag on its own is inert (no fake video device appears at all).
// Faking the camera that way would therefore take out both halves of the audio path — the
// `gavel_out` monitor we record the room from, and the `gavel_in.monitor` Chromium uses as its
// microphone — so it is unusable here. Patching `getUserMedia` touches video and nothing else.
//
// There is no video generation anywhere in this: the frames are one image, redrawn.
(() => {
  const FACE = __FACE__;
  const LABEL = __LABEL__;
  const W = __W__, H = __H__, FPS = __FPS__;
  const DEVICE_ID = "gavel-face-still";
  const GROUP_ID = "gavel-face";

  const md = navigator.mediaDevices;
  if (!md || typeof md.getUserMedia !== "function") return;

  let source = null;
  const canvasStream = () => {
    if (source) return source;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    const img = new Image();
    // ffmpeg has already letterboxed the still to exactly W x H, so this is a straight blit.
    const draw = () => {
      if (img.complete && img.naturalWidth) ctx.drawImage(img, 0, 0, W, H);
      else { ctx.fillStyle = "#1b1b1f"; ctx.fillRect(0, 0, W, H); }
    };
    img.onload = draw;
    img.src = FACE;
    draw();
    // A canvas only emits a frame when something draws on it. Redrawing the same picture
    // keeps the track live instead of frozen; what the room sees never changes.
    setInterval(draw, Math.round(1000 / FPS));
    source = canvas.captureStream(FPS);
    return source;
  };

  // A fresh MediaStream each call, with its own clone of the track: closing one call's
  // stream must not stop the shared canvas source.
  const faceTrack = () => canvasStream().getVideoTracks()[0].clone();

  const wantsFace = (video) => {
    if (!video) return false;
    const want = video.deviceId;
    const id = want && typeof want === "object" ? want.exact || want.ideal : want;
    // An explicit request for some other device is not ours to answer.
    return typeof id !== "string" || !id || id === DEVICE_ID;
  };

  const originalGetUserMedia = md.getUserMedia.bind(md);
  md.getUserMedia = async (constraints) => {
    const wanted = constraints || {};
    if (!wantsFace(wanted.video)) return originalGetUserMedia(wanted);
    const stream = new MediaStream();
    stream.addTrack(faceTrack());
    if (wanted.audio) {
      // The microphone stays real: it is the PulseAudio monitor the chair speaks through.
      const audio = await originalGetUserMedia({ audio: wanted.audio });
      audio.getAudioTracks().forEach((track) => stream.addTrack(track));
    }
    return stream;
  };

  // Meet will not offer a camera at all unless one enumerates.
  const device = { deviceId: DEVICE_ID, groupId: GROUP_ID, kind: "videoinput", label: LABEL };
  device.toJSON = () => ({ ...device });
  const originalEnumerateDevices = md.enumerateDevices.bind(md);
  md.enumerateDevices = async () => {
    const devices = await originalEnumerateDevices();
    return devices.some((d) => d.deviceId === DEVICE_ID) ? devices : devices.concat([device]);
  };
})();
