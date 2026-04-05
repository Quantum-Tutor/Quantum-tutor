// sw.js
// Basic service worker to satisfy PWA installability requirements
self.addEventListener('install', event => {
  console.log('Quantum Tutor SW installed');
});

self.addEventListener('fetch', event => {
  // Pass-through
});
