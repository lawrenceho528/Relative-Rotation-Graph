# Reference Alignment

The chart intentionally mirrors StockCharts' Relative Rotation Graph behavior at
https://stockcharts.com/freecharts/rrg and the TradingView Pine-style EMA conventions.

## Implemented behavior

- Relative strength: `RS = asset close / SPY close`.
- RS-Ratio: `EMA(RS / EMA(RS, Length), Smooth) * 100`, plotted on the horizontal axis around 100.
- RS-Momentum: `RS-Ratio / EMA(RS-Ratio, Smooth) * 100`, plotted on the vertical axis around 100.
- Quadrants: Leading, Weakening, Lagging, Improving, all centered on 100/100.
- Fixed default scale from 90 to 110 with pannable/zoomable viewport.
- Fading tail history dots and smooth tail curves ending at the selected date.
- Length and Smooth selectors using Pine-style EMA periods (10, 14, 20, 50, 100, 150, 200).

## Interaction alignment

- Horizontal time scrubbing: dragging inside the chart pans the viewport without changing
  the selected date; the date slider, previous/next buttons, and playback control time.
- Two-finger pinch zooms and pans the chart continuously; single-finger drag pans.
- Tapping a marker or a ranking row selects that symbol and updates the detail panel.
- Individual symbols can be hidden/shown; Hide All and Show All are provided.

The precomputed `rrg` payload in `public/data/rrg.json` and the browser-side
`computeRrgPoints` recalculation implement the identical Pine-style formula, so changing
Length, Smooth, or timeframe always recalculates from the bundled daily closes.
