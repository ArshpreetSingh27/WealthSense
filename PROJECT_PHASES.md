# Project phases — paper trading and portfolio management

The product is a multi-user paper trading and portfolio management application. Each user has a separate virtual trading account and may track manually entered holdings. The app does not connect to a broker or place real orders.

## Phase 1 — Account and data safety

- [x] Per-user login, isolated portfolio data, and authenticated API mutations.
- [x] Reject stale market data, fix renamed symbols and training label leakage, and remove fabricated price targets.
- [x] Keep account API responses uncached and prevent untrusted headline markup from running in the page.
- [ ] Before public deployment: persistent application secret, HTTPS, database backups and migrations, concurrency tests, and source control.

## Phase 2 — Manual portfolio tracking

- [x] Per-user manually entered holdings with latest available valuations and estimated P&L.
- [ ] Add portfolio performance history and clearer handling of splits, dividends, and unavailable prices.

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

No broker connection or real order worker is part of the planned system.
