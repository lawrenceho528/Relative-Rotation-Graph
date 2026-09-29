# iPad Install Checklist

1. Host the built artifact (`scripts/package-dist.ps1` output) on an HTTPS static host,
   or serve `dist/` locally for preview.
2. Run `scripts/install-preflight.ps1 -BaseUrl <url>` and confirm it passes before
   handing the URL to the iPad.
3. On the iPad, open the URL in Safari (not Chrome; the Home Screen flow is Safari-only).
4. Tap the Share button and choose "Add to Home Screen".
5. Confirm the name shows `RRG` and the icon matches `icons/icon-192.png`.
6. Launch the app from the Home Screen; it must open without Safari chrome
   (standalone display mode).
7. Confirm the status pill shows "RRG data loaded" and "Last updated" is recent.
8. Verify interactions: universe tabs, timeframe tabs, Length/Smooth selectors, tail
   slider, date slider, play/pause, hide/show, pinch zoom, and single-finger pan.
9. Turn Wi-Fi off and reload: the service worker must keep serving the last real data
   (network-first cache with offline fallback).
10. Reconnect Wi-Fi and pull the newest data by tapping the refresh button; confirm
    "Last updated" advances.
