const CACHE_NAME = "rgg-rotation-v2";
const APP_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./src/app.js",
  "./data/rrg.json",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/apple-touch-icon.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => Promise.all(APP_ASSETS.map((asset) => cache.add(asset).catch(() => null)))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (url.pathname.endsWith("/data/rrg.json") || url.pathname.endsWith("/public/data/rrg.json")) {
    const cacheKey = new Request(new URL("data/rrg.json", self.registration.scope).toString());
    event.respondWith(networkFirst(request, cacheKey));
    return;
  }

  if (url.pathname.endsWith("/build-info.json")) {
    const cacheKey = new Request(new URL("build-info.json", self.registration.scope).toString());
    event.respondWith(networkFirst(request, cacheKey));
    return;
  }

  if (request.method === "GET" && url.origin === self.location.origin) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(fetch(request));
});

async function networkFirst(request, cacheKey = request) {
  try {
    const response = await fetch(request);
    const copy = response.clone();
    const cache = await caches.open(CACHE_NAME);
    await cache.put(cacheKey, copy);
    return response;
  } catch {
    const cached = await caches.match(cacheKey);
    if (cached) return cached;
    throw new Error(`No cached response for ${request.url}`);
  }
}
