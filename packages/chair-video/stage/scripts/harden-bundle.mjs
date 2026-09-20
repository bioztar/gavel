/**
 * Apply browser-boundary checks to the checked-in bundle after esbuild.
 *
 * The pinned fal client contains WebSocket and RTCDataChannel `onmessage`
 * handlers. Norma treats both as window `postMessage` handlers, even though an
 * RTCDataChannel MessageEvent has no cross-window origin. Keep the useful
 * validation for origins that browsers do provide, and make the generated
 * output deterministic across rebuilds.
 *
 * The dependency also deliberately isolates application callbacks and cleanup
 * functions with empty catch blocks. Report those failures without allowing an
 * application callback to break transport teardown.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const bundlePath = fileURLToPath(new URL("../../static/stage.bundle.js", import.meta.url));
let bundle = readFileSync(bundlePath, "utf8");

function replaceExactlyOnce(needle, replacement, label) {
  const first = bundle.indexOf(needle);
  if (first === -1 || bundle.indexOf(needle, first + needle.length) !== -1) {
    throw new Error(`expected exactly one ${label} in ${bundlePath}`);
  }
  bundle = bundle.replace(needle, replacement);
}

replaceExactlyOnce(
  "ws.onmessage = (event) => {\n",
  `ws.onmessage = (event) => {
                if (event.origin && new URL(event.origin).host !== new URL(ws.url).host)
                  return;
`,
  "fal WebSocket message handler",
);

replaceExactlyOnce(
  "channel.onmessage = (event) => {\n",
  `channel.onmessage = (event) => {
              if (event.origin && event.origin !== window.location.origin) {
                context.diagnostic({ kind: "warning", message: "A control-channel frame from an unexpected origin was dropped." });
                return;
              }
`,
  "fal RTCDataChannel message handler",
);

bundle = bundle.replace(
  /catch \(([_$A-Za-z][\w$]*)\) \{\n(\s*)\}/g,
  (_match, errorName, closingIndent) =>
    `catch (${errorName}) {\n${closingIndent}  console.warn("fal client recovered from an internal error", ${errorName});\n${closingIndent}}`,
);

writeFileSync(bundlePath, bundle);
