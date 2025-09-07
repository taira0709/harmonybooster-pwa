/* Harmony Booster PWA Service Worker (v1.1)
   - HTML: network-first（オフライン時のみキャッシュを返す）
   - 静的ファイル: cache-first（初回にプリキャッシュ）
   - 非GET/処理系パス: 常に素通し（キャッシュしない）
   使い方：
   1) 静的を更新したら CACHE_VERSION を上げる（例: v1.2）
   2) API ルートを変えたら BYPASS_CACHE_PATH_PREFIXES を合わせる
*/

// ====== バージョン管理 ======
const CACHE_VERSION = 'v1.1';
const CACHE_PREFIX  = 'hb-static-';
const CACHE_NAME    = `${CACHE_PREFIX}${CACHE_VERSION}`;

// ====== プリキャッシュする静的アセット ======
const STATIC_ASSETS = [
  '/',                          // ルート（index.html に解決）
  '/static/manifest.json',
  '/static/icon.png',           // 192x192
  '/static/icon-512.png',       // 512x512
  '/static/style.css'           // あれば
];

// ====== キャッシュを回避するパス（先頭一致） ======
const BYPASS_CACHE_PATH_PREFIXES = [
  '/process',                   // 音声処理POSTなど
  '/download',                  // ダウンロード系
  '/api/',                      // API を増やしたらここに追記
  '/sw.js'                      // SW自身
];

// ====== install: プリキャッシュ ======
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ====== activate: 古いバージョンのキャッシュを掃除 ======
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ====== fetch: ルーティング戦略 ======
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1) 非GETはキャッシュしない（処理系は常に素通し）
  if (req.method !== 'GET') {
    return; // デフォルト挙動 = ネットワークへ
  }

  // 2) 指定パスはキャッシュ回避
  if (BYPASS_CACHE_PATH_PREFIXES.some((p) => url.pathname.startsWith(p))) {
    return; // ネットワークへ
  }

  // 3) HTML（ナビゲーション）は network-first
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(networkFirst(req));
    return;
  }

  // 4) 同一オリジンの静的は cache-first（更新はバックグラウンドで）
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // 5) クロスオリジンは素通し
  // （必要があればここで別戦略に切替）
});

// ---- strategies ----
async function networkFirst(req) {
  try {
    const fresh = await fetch(req, { cache: 'no-store' });
    // ルートHTMLのみキャッシュに保存（任意）
    const cache = await caches.open(CACHE_NAME);
    cache.put(req, fresh.clone());
    return fresh;
  } catch (_err) {
    const cache = await caches.open(CACHE_NAME);
    // ルートが欲しいケースに備えて '/' も見る
    return (await cache.match(req)) || (await cache.match('/')) || Response.error();
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  if (cached) {
    // バックグラウンドで更新（失敗は無視）
    fetch(req).then((res) => {
      if (res && res.ok) cache.put(req, res.clone());
    }).catch(() => {});
    return cached;
  }
  const res = await fetch(req);
  if (res && res.ok) cache.put(req, res.clone());
  return res;
}
