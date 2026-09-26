const JANUS_SCOPE = '/app/';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method === 'GET' && event.request.url.startsWith(self.location.origin + JANUS_SCOPE)) {
    event.respondWith(fetch(event.request));
  }
});
