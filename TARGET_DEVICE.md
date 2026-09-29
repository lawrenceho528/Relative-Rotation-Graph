# Target Device

The app is tuned for the following iPad as the primary target:

- Device: iPad mini (A17 Pro)
- Model identifier: A2993
- Display: 2266-by-1488 resolution at 326 ppi
- Logical portrait viewport: 744 x 1133
- Logical landscape viewport: 1133 x 744
- Safari with `user-scalable=no` and `maximum-scale=1`; added to the Home Screen as a
  standalone PWA via `manifest.webmanifest` and `apple-mobile-web-app-capable`.

## Verification proxies

- Layout audits assume portrait 744 x 1133 and landscape 1133 x 744 CSS pixels.
- Screenshot audits capture those viewports with deviceScaleFactor 1-2.
- Touch audits emulate `maxTouchPoints = 5`.
- The performance budget uses the same viewport as the device proxy.

Any other iPad or browser window still works; only pixel-perfect layout guarantees are
scoped to the target device above.
