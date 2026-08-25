// Cache minimo per mantenere la UI disponibile anche durante un breve riavvio del gateway.
const CACHE = "nova5-field-control-v6";
const ASSETS = [
  "/",
  "/assets/styles.css",
  "/assets/app.js",
  "/assets/manifest.webmanifest",
];
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting()),
  );
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  // L'interfaccia di comando non deve restare su JavaScript obsoleto dopo un
  // aggiornamento: preferiamo la rete e usiamo la cache solo durante un
  // riavvio momentaneo del gateway.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request)),
  );
});
