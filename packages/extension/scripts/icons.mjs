// Draws the toolbar icons at build time so no binary lives in the repo.
// A hand-rolled PNG encoder (zlib + CRC32) is ~40 lines; a rasterizer dependency
// would be more code than this whole file.
import { deflateSync } from "node:zlib";
import { writeFile } from "node:fs/promises";
import path from "node:path";

const ACCENT = [0x00, 0x71, 0xe3, 0xff];
const WHITE = [0xff, 0xff, 0xff, 0xff];
const CLEAR = [0, 0, 0, 0];

const CRC_TABLE = new Int32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});

function crc32(buf) {
  let c = -1;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function encodePng(size, pixelAt) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0; // filter: none
    for (let x = 0; x < size; x++) {
      const [r, g, b, a] = pixelAt(x, y);
      const o = y * (size * 4 + 1) + 1 + x * 4;
      raw[o] = r;
      raw[o + 1] = g;
      raw[o + 2] = b;
      raw[o + 3] = a;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// A rounded accent tile with a gavel head (thick bar, upper left) and a
// handle (thin diagonal, lower right). Legible at 16px, which is the test.
function gavelPixel(size) {
  const r = size * 0.22;
  const inside = (x, y) => {
    const cx = Math.min(Math.max(x + 0.5, r), size - r);
    const cy = Math.min(Math.max(y + 0.5, r), size - r);
    return (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r;
  };
  return (x, y) => {
    if (!inside(x, y)) return CLEAR;
    const u = (x + 0.5) / size;
    const v = (y + 0.5) / size;
    // head: rotated 45° rectangle centred at (0.42, 0.42)
    const hx = (u - 0.42 + (v - 0.42)) / Math.SQRT2;
    const hy = (v - 0.42 - (u - 0.42)) / Math.SQRT2;
    if (Math.abs(hx) < 0.24 && Math.abs(hy) < 0.11) return WHITE;
    // handle: from the head down to the lower-right corner
    const t = (u - 0.5 + (v - 0.5)) / Math.SQRT2;
    const n = (v - 0.5 - (u - 0.5)) / Math.SQRT2;
    if (t > 0.02 && t < 0.36 && Math.abs(n) < 0.055) return WHITE;
    return ACCENT;
  };
}

export async function writeIcons(dir) {
  await Promise.all(
    [16, 48, 128].map((size) =>
      writeFile(path.join(dir, `icon-${size}.png`), encodePng(size, gavelPixel(size))),
    ),
  );
}
