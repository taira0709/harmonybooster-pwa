// static/sw.js
const VERSION = "hb-v2";                 // ← 更新時はここを上げる
const STATIC_CACHE = `static-${VERSION}`;
const APP_SHELL = [
  "/",                         // ルート
  "/static/manifest.json",
  "/static/style.css",
  "/static/icon.png",
  "/static/icon-512.png"
  // 必要ならJSや画像を追加
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(STATIC_CACHE).then((c) => c.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k !== STATIC_CACHE ? caches.delete(k) : null)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  // まずキャッシュ、裏で最新取得（stale-while-revalidate 風）
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetchPromise = fetch(e.request)
        .then((res) => {
          if (res && res.status === 200 && res.type === "basic") {
            caches.open(STATIC_CACHE).then((c) => c.put(e.request, res.clone()));
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
