// Optional art/audio. Drop files into web/assets/ using the names below; missing files are ignored.
//   web/assets/art/<scene-art-key>.jpg   e.g. arrival.jpg, sun_market.jpg
//   web/assets/audio/<music-key>.mp3     e.g. city_dark.mp3, market_tension.mp3, combat.mp3

const cache = new Map();

function probe(url) {
  if (!cache.has(url)) {
    cache.set(url, new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(url);
      img.onerror = () => resolve(null);
      img.src = url;
    }));
  }
  return cache.get(url);
}

export async function applySceneArt(el, key) {
  const url = await probe(`assets/art/${key}.jpg`);
  el.style.backgroundImage = url ? `url("${url}")` : "";
  el.classList.toggle("has-art", Boolean(url));
}

// ---------- Music ----------
// Tracks are keyed by music id. Keys without a track simply fade out whatever is playing.
const TRACKS = {
  agnivara: { src: "assets/audio/agnivara.mp3", title: "For Blood, for Glory, for Honor" },
};
const VOLUME = 0.55;
const audio = new Audio();
audio.loop = true;
audio.preload = "none";
let currentKey = null;
let muted = false;
let blocked = false;
let fadeTimer = null;
const listeners = new Set();
try { muted = localStorage.getItem("musicMuted") === "1"; } catch {}

function notify() {
  const st = musicState();
  listeners.forEach((fn) => fn(st));
}

function fadeTo(target, ms, done) {
  clearInterval(fadeTimer);
  const start = audio.volume, steps = Math.max(1, Math.round(ms / 50));
  let i = 0;
  fadeTimer = setInterval(() => {
    i += 1;
    audio.volume = Math.min(1, Math.max(0, start + (target - start) * (i / steps)));
    if (i >= steps) { clearInterval(fadeTimer); if (done) done(); }
  }, 50);
}

async function startPlayback() {
  if (muted || !currentKey || !TRACKS[currentKey]) return;
  try {
    audio.volume = 0;
    await audio.play();
    blocked = false;
    fadeTo(VOLUME, 1500);
  } catch {
    blocked = true; // browser wants a tap first
  }
  notify();
}

export function setMusic(key) {
  const track = TRACKS[key] ? key : null;
  if (track === currentKey) return;
  currentKey = track;
  if (!track) {
    if (!audio.paused) fadeTo(0, 1200, () => audio.pause());
    blocked = false;
    notify();
    return;
  }
  const next = TRACKS[track];
  const begin = () => { audio.src = next.src; audio.currentTime = 0; startPlayback(); };
  if (!audio.paused) fadeTo(0, 600, () => { audio.pause(); begin(); });
  else begin();
}

export function toggleMusic() {
  if (blocked && !muted) { startPlayback(); return; } // first tap after an autoplay block
  muted = !muted;
  try { localStorage.setItem("musicMuted", muted ? "1" : "0"); } catch {}
  if (muted) fadeTo(0, 400, () => audio.pause());
  else startPlayback();
  notify();
}

export function musicState() {
  const t = currentKey ? TRACKS[currentKey] : null;
  return { playing: !!t && !audio.paused && !muted, title: t?.title || null, muted, blocked: blocked && !muted };
}

export function onMusicChange(fn) {
  listeners.add(fn);
  fn(musicState());
}
