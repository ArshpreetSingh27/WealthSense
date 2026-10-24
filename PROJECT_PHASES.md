# Project phases — paper trading and read-only Kite sync

The product is a multi-user paper trading and portfolio management application. Each user has a separate virtual trading account. A connected Zerodha account supplies read-only holdings, positions, funds, and order history. The app does not place broker orders, and live trading is outside this project.

## Phase 1 — Account and data safety

- [x] Per-user login, encrypted Kite tokens, callback state checks, and authenticated API mutations.
- [x] Reject stale market data, fix renamed symbols and training label leakage, and remove fabricated price targets.
- [x] Keep account API responses uncached and prevent untrusted headline markup from running in the page.
- [ ] Before public deployment: persistent application secret, HTTPS, database backups and migrations, concurrency tests, and source control.

## Phase 2 — Kite portfolio sync

- [x] Per-user read-only connect, holdings, positions, funds, orders, refresh, reconnect, and disconnect.
- [ ] Verify two real Kite accounts with approved app credentials; reconcile balances and corporate actions against Kite.
- [ ] Add bounded retries, provider rate control, monitoring, and dated broker snapshots if required.

## Phase 3 — Per-user paper trading

- [x] Separate virtual cash, long-only positions, trade history, and account deletion for every user.
- [x] Manual virtual orders at the latest available NSE close, with 0.12% modeled execution friction, an order ID to prevent duplicate fills, and a 20% maximum per-stock position.
- [x] User opt-in paper bot: up to three new 5% buys per daily run, SELL signal exits, ten-position limit, repeat-run protection, and a per-user pause switch.
- [x] Keep the old shared paper task disabled. Its historical file is retained only for reference and is never exposed as a user's account.
- [ ] Add an account-level performance series, an explicit simulation audit report, and more realistic exchange calendar and charge handling.

## Phase 4 — Research validation and deployment

- [ ] Remove placeholder strategy features and test the signals with purged walk-forward validation, costs, benchmark comparisons, and forward paper results.
- [ ] Set documented acceptance criteria before representing a strategy as reliable. A September 2026 holdout check of the current daily classifier was about 49.7% accurate.
- [ ] Deploy the paper-only website with production security and confirm recurring jobs on the host.

No live Kite order endpoint or broker order worker is part of the planned system.
