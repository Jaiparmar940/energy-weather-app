import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

const srcDir = path.join(root, 'data', 'exports');
const destDir = path.join(root, 'public', 'data');

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function copyFile(src, dest) {
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function rmDirIfExists(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function listFilesRecursive(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  const stack = [dir];
  while (stack.length) {
    const cur = stack.pop();
    const entries = fs.readdirSync(cur, { withFileTypes: true });
    for (const e of entries) {
      const full = path.join(cur, e.name);
      if (e.isDirectory()) stack.push(full);
      else if (e.isFile()) out.push(full);
    }
  }
  return out;
}

function syncOnce() {
  if (!fs.existsSync(srcDir)) {
    console.log(`[sync] No exports found at ${srcDir}`);
    console.log('[sync] Run your export scripts to generate JSON into data/exports/');
    return;
  }

  ensureDir(destDir);

  // Clean only files we manage (keep any manual readme, etc.)
  // We'll remove and recreate the folder for simplicity.
  rmDirIfExists(destDir);
  ensureDir(destDir);

  const files = listFilesRecursive(srcDir);
  let copied = 0;
  for (const f of files) {
    const rel = path.relative(srcDir, f);
    copyFile(f, path.join(destDir, rel));
    copied += 1;
  }
  console.log(`[sync] Copied ${copied} files from data/exports → public/data`);
}

syncOnce();

