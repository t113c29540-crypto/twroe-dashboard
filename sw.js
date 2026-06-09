// 台股高ROE 行動看板 — Service Worker(離線快取 + Web Push)
const CACHE = 'twroe-v3';
const SHELL = ['./', './index.html', './manifest.webmanifest',
  './icon-192.png', './icon-512.png', './apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin || e.request.method !== 'GET') return; // 跨網域(報價/新聞)走網路
  const isHTML = e.request.mode === 'navigate' || u.pathname.endsWith('.html') || u.pathname.endsWith('/');
  if (isHTML) {
    // HTML 用 network-first:永遠拿最新版本,離線才退回快取
    e.respondWith(
      fetch(e.request).then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(e.request, c)); return r; })
        .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
    );
  } else {
    // 靜態資產(圖示/manifest)cache-first
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});

// ===== Web Push:即使關閉 App 也能收到 =====
self.addEventListener('push', e => {
  let d = { title: '🟢 台股高ROE 到價買訊', body: '有股票跌到便宜價', url: './index.html' };
  try { d = Object.assign(d, e.data.json()); } catch (_) { if (e.data) d.body = e.data.text(); }
  e.waitUntil(self.registration.showNotification(d.title, {
    body: d.body, icon: './icon-192.png', badge: './icon-192.png',
    data: { url: d.url }, vibrate: [80, 40, 80], tag: d.tag || 'twroe'
  }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || './index.html';
  e.waitUntil(clients.matchAll({ type: 'window' }).then(ws => {
    for (const w of ws) { if ('focus' in w) return w.focus(); }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
