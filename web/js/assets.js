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

// Music hook for a later stage. Kept as a no-op so the game runs with no audio files.
export function setMusic(_key) {}
