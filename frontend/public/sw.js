/* Verda service worker — minimal, network-first.
 *
 * The Verda runtime intentionally does not phone home. The service
 * worker mirrors that posture: it does not pre-fetch, it does not
 * subscribe to push, it does not register background sync. Its only
 * jobs are:
 *
 *   1. Cache the static asset shell (logo, manifest, icons, public SVGs)
 *      so the PWA boots even when the network is flaky.
 *   2. Pass every authenticated API call (`/api/*`) through to the
 *      network without caching — auth tokens, case data, and IAM
 *      decisions must always be live.
 *   3. Serve a small offline fallback when navigation requests fail.
 *
 * Activate flow:
 *   - Each new SW version uses a fresh CACHE_NAME so old caches are
 *     cleaned up on `activate`.
 *   - `clients.claim()` makes the new worker control existing tabs
 *     immediately so an upgrade reaches the user without a hard reload.
 */

const CACHE_NAME = "verda-v1";
const STATIC_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/verda-mark.svg",
  "/hero-illustration.svg",
  "/motif-evidence.svg",
  "/motif-scales.svg",
  "/partners/osf-placeholder.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never cache POST/PATCH/DELETE/PUT
  const url = new URL(request.url);

  // Same-origin only — never cache OIDC redirects, Keycloak HTML, etc.
  if (url.origin !== self.location.origin) return;

  // Authenticated and dynamic — always go to network. Auth, case data,
  // permission lookups, exports must never come from a stale cache.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/_next/data/") ||
    url.pathname.startsWith("/_next/image")
  ) {
    return;
  }

  // Static asset / shell route — network-first, fall back to cache, then
  // to the cached shell as offline failover.
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Cache successful, basic, same-origin GET responses.
        if (response && response.status === 200 && response.type === "basic") {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          return caches.match("/");
        }
        return new Response("offline", {
          status: 503,
          statusText: "Service Unavailable",
        });
      })
  );
});
