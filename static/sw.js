// Service Worker (HTMLは絶対キャッシュしない・既存キャッシュは全削除)
const VERSION = "hb-v3"; // 変更時に上げる

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    // 旧バージョンのキャッシュをすべて削除
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const accept = req.headers.get("accept") || "";

  // HTML/ナビゲーションは常にネットワーク（= 認証が必ず要求される）
  if (req.mode === "navigate" || accept.includes("text/html")) {
    event.respondWith(fetch(req, { cache: "no-store" }));
    return;
  }

  // それ以外は素通り（必要ならここに静的資産のキャッシュ戦略を追加）
  event.respondWith(fetch(req));
});
