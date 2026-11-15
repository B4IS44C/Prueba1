self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let d = { title: "Monitor SINPE", body: "", url: "/" };
  try { d = { ...d, ...event.data.json() }; } catch (_) {}
  event.waitUntil(
    self.registration.showNotification(d.title, {
      body: d.body,
      icon: "/static/icon-192.png",
      badge: "/static/icon-192.png",
      data: { url: d.url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) if ("focus" in c) return c.focus();
      return clients.openWindow(url);
    })
  );
});
