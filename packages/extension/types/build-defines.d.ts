// Compile-time constants injected by scripts/build.mjs (esbuild `define`).
// `__DEV_BUILD__` is true only for `npm run build:dev`; the production bundle
// has every branch guarded by it removed.
declare const __DEV_BUILD__: boolean;
declare const __EXTENSION_VERSION__: string;

declare module "*.css" {
  const text: string;
  export default text;
}
