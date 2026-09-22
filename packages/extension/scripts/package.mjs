// Zips dist/ into a store-ready upload for Chrome Web Store / Edge Add-ons.
// No compression library dependency: a ZIP with STORE-method entries is a
// valid ZIP (the format doesn't require DEFLATE), and this is ~90 lines of
// buffer-writing, the same call made for the icons in icons.mjs.
//
// Run `npm run build` first (or use `npm run package`, which does both) —
// this script only zips whatever is already in dist/, so a stale dist/ zips
// stale content.
import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dist = path.join(root, "dist");

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

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(p)));
    else out.push(p);
  }
  return out;
}

// MS-DOS date/time, fixed rather than derived from the current clock — a
// build of the same source produces byte-identical output.
const DOS_TIME = 0;
const DOS_DATE = (1980 - 1980) << 9 | (1 << 5) | 1;

function zip(entries) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const { name, data } of entries) {
    const nameBuf = Buffer.from(name, "utf8");
    const crc = crc32(data);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4); // version needed
    local.writeUInt16LE(0, 6); // flags
    local.writeUInt16LE(0, 8); // method: stored
    local.writeUInt16LE(DOS_TIME, 10);
    local.writeUInt16LE(DOS_DATE, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    localParts.push(local, nameBuf, data);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4); // version made by
    central.writeUInt16LE(20, 6); // version needed
    central.writeUInt16LE(0, 8); // flags
    central.writeUInt16LE(0, 10); // method: stored
    central.writeUInt16LE(DOS_TIME, 12);
    central.writeUInt16LE(DOS_DATE, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt16LE(0, 30); // extra length
    central.writeUInt16LE(0, 32); // comment length
    central.writeUInt16LE(0, 34); // disk number
    central.writeUInt16LE(0, 36); // internal attrs
    central.writeUInt32LE(0o644 << 16, 38); // external attrs (unix perms)
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, nameBuf);

    offset += local.length + nameBuf.length + data.length;
  }

  const centralStart = offset;
  const centralBuf = Buffer.concat(centralParts);

  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(0, 4);
  end.writeUInt16LE(0, 6);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralBuf.length, 12);
  end.writeUInt32LE(centralStart, 16);
  end.writeUInt16LE(0, 20);

  return Buffer.concat([...localParts, centralBuf, end]);
}

if (!(await stat(dist).catch(() => null))) {
  console.error(`package: ${path.relative(root, dist)}/ does not exist — run \`npm run build\` first`);
  process.exit(1);
}

// A previous run's zip lives in dist/ — never package it into the next one.
const files = (await walk(dist)).filter((f) => !f.endsWith(".zip")).sort();
const entries = await Promise.all(
  files.map(async (file) => ({
    name: path.relative(dist, file).split(path.sep).join("/"),
    data: await readFile(file),
  })),
);

const manifest = JSON.parse(await readFile(path.join(dist, "manifest.json"), "utf8"));
const outPath = path.join(dist, `gavel-extension-${manifest.version}.zip`);
await writeFile(outPath, zip(entries));

const totalBytes = entries.reduce((sum, e) => sum + e.data.length, 0);
console.log(`packaged → ${path.relative(root, outPath)} (${entries.length} files, ${totalBytes} bytes)`);
