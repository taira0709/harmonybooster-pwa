// Service Worker: HTMLは常にネットワーク、APIは素通し、古いキャッシュは全削除
const VERSION = "hb-v6";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k))); // 既存キャッシュ全破棄
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // POST等は触らない（= APIは常にネットワークへ）
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  const accept = req.headers.get("accept") || "";

  // /api/ は GET でもキャッシュしない（ストリーミング応答対策）
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(req, { cache: "no-store" }));
    return;
  }

  // HTML/ナビゲーションは常にネットワーク
  if (req.mode === "navigate" || accept.includes("text/html")) {
    event.respondWith(fetch(req, { cache: "no-store" }));
    return;
  }

  // その他は素通し（必要に応じて静的資産のキャッシュ戦略を足す）
  event.respondWith(fetch(req));
});
