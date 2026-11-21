/**
 * Build WCAG-legible KC Ledger app icons without third-party image tooling.
 * Source files are generated at build/dev time and copied by Vite into dist/pwa.
 * PNG files are generated public assets, not private user data.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { deflateSync } from "node:zlib";

const BLUE = [56, 189, 248, 255];
const NAVY = [11, 27, 61, 255];
const PAPER = [245, 245, 247, 255];
const SOFT = [119, 145, 185, 255];
const LETTERS = {
    K: ["10001","10010","10100","11000","10100","10010","10001"],
    C: ["01111","10000","10000","10000","10000","10000","01111"],
};
function crc32(data) {
    let c = 0xffffffff;
    for (const byte of data) {
        c ^= byte;
        for (let j = 0; j < 8; j++) c = (c >>> 1) ^ ((c & 1) ? 0xedb88320 : 0);
    }
    return (c ^ 0xffffffff) >>> 0;
}
function chunk(name, contents) {
    const label = Buffer.from(name, "ascii");
    const len = Buffer.alloc(4);
    len.writeUInt32BE(contents.length, 0);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([label, contents])), 0);
    return Buffer.concat([len, label, contents, crc]);
}
function png(width, height, bytes) {
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(width, 0);
    ihdr.writeUInt32BE(height, 4);
    ihdr[8] = 8; // RGBA truecolor, alpha channel
    ihdr[9] = 6;
    return Buffer.concat([
        Buffer.from("89504e470d0a1a0a", "hex"),
        chunk("IHDR", ihdr),
        chunk("IDAT", deflateSync(bytes, { level: 9 })),
        chunk("IEND", Buffer.alloc(0))
    ]);
}
function draw(size, maskable = false) {
    const scanlines = Buffer.alloc(size * (1 + size * 4));
    const unit = size / 512;
    const radius = size * (maskable ? 0.15 : 0.18);
    const inset = size * (maskable ? 0.12 : 0.035);
    const tileLeft = inset;
    const tileRight = size - inset;
    const tileTop = inset;
    const tileBottom = size - inset;
    const center = size / 2;
    const drawLetter = (letter, left, top, pixel) => {
        const pattern = LETTERS[letter];
        for (let r = 0; r < pattern.length; r++) {
            for (let col = 0; col < pattern[r].length; col++) {
                if (pattern[r][col] !== "1") continue;
                for (let y = Math.max(0, Math.floor(top + r * pixel)); y < Math.min(size, Math.ceil(top + (r + 1) * pixel)); y++) {
                    for (let x = Math.max(0, Math.floor(left + col * pixel)); x < Math.min(size, Math.ceil(left + (col + 1) * pixel)); x++) {
                        const offset = y * (1 + size * 4) + 1 + x * 4;
                        // Filter boundaries match only whole pixel blocks.
                        BLUE.forEach((value, channel) => { scanlines[offset + channel] = value; });
                    }
                }
            }
        }
    };
    const radiusSquared = radius * radius;
    for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
            const px = x + 0.5;
            const py = y + 0.5;
            const cx = Math.min(Math.max(px, tileLeft + radius), tileRight - radius);
            const cy = Math.min(Math.max(py, tileTop + radius), tileBottom - radius);
            const inTile = (px - cx) ** 2 + (py - cy) ** 2 <= radiusSquared;
            const border =
                (px > tileLeft + size * 0.052 && px < tileRight - size * 0.052 &&
                    py > tileTop + size * 0.052 && py < tileBottom - size * 0.052) &&
                (px < tileLeft + size * 0.064 || px > tileRight - size * 0.064 ||
                    py < tileTop + size * 0.064 || py > tileBottom - size * 0.064);
            const offset = y * (1 + size * 4) + 1 + x * 4;
            const color = inTile ? border ? SOFT : NAVY : maskable ? NAVY : PAPER;
            scanlines[offset] = color[0];
            scanlines[offset + 1] = color[1];
            scanlines[offset + 2] = color[2];
            scanlines[offset + 3] = color[3];
        }
    }
    const pixel = size * (maskable ? 0.054 : 0.065);
    const spacing = pixel * 1.2;
    const total = 10 * pixel + spacing;
    const top = center - 3.5 * pixel;
    drawLetter("K", center - total / 2, top, pixel);
    drawLetter("C", center - total / 2 + 5 * pixel + spacing, top, pixel);
    return png(size, size, scanlines);
}
mkdirSync("public/pwa", { recursive: true });
for (const [filename, size, maskable] of [
    ["icon-192.png", 192, false],
    ["icon-512.png", 512, false],
    ["maskable-512.png", 512, true],
    ["apple-touch-icon.png", 180, false],
    ["favicon-32.png", 32, false],
]) {
    const bytes = draw(size, maskable);
    writeFileSync("public/pwa/" + filename, bytes);
    console.info("PWA icon:", filename, bytes.length, "bytes");
}
