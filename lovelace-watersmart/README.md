# WaterSmart Card

A companion Lovelace card for the [WaterSmart integration][integration-repo]:
an hourly usage bar chart with utility-reported **leak hours highlighted in
red**, plus a GitHub-contribution-style **daily heatmap**.

Zero dependencies, no build step — `watersmart-card.js` is the distributable.

## Install

Until this folder is split into its own repository, install manually:

1. Copy `watersmart-card.js` to `/config/www/watersmart-card.js` in your Home
   Assistant configuration.
2. Add a dashboard resource: _Settings → Dashboards → ⋮ → Resources_ →
   _+ Add resource_ → URL `/local/watersmart-card.js`, type _JavaScript module_.
3. Add the card to a dashboard (below). Requires a Home Assistant core new
   enough for service responses (`return_response`, 2023.7+) — the same floor
   as the integration itself.

## Usage

```yaml
type: custom:watersmart-card
title: Water usage
hours: 48    # hourly bar chart depth (default 48, max 336)
weeks: 12    # heatmap depth (default 12, max 26)
```

| Option  | Type   | Default | Description                                                                 |
| ------- | ------ | ------- | --------------------------------------------------------------------------- |
| `title` | string | `Water usage` | Card title.                                                           |
| `entry` | string | auto    | Config entry id. Only needed with multiple WaterSmart accounts; the card lists candidate ids in its error message when ambiguous. |
| `hours` | number | `48`    | How many hourly bars to render.                                             |
| `weeks` | number | `12`    | How many weeks of heatmap cells to render.                                  |
| `unit`  | string | `auto`  | `auto` follows the Home Assistant unit system (`gal`/`L`); or force `gal`/`L`. |

Data comes from the integration's `watersmart.get_hourly_history` service
(response includes `leak_gallons` per hour), fetched with `cached: true` so
dashboard loads never trigger upstream refreshes. The card re-fetches every 10
minutes and exposes a retry button on failures.

## Development

No toolchain. Edit `watersmart-card.js` directly. A self-contained harness with
a mocked Home Assistant connection lives at `test/harness.html`:

```sh
open test/harness.html   # any browser; asserts render in the console-free path
```

## Splitting into its own HACS repository

This folder is structured to become a standalone HACS plugin repo:

1. Move this folder's contents to a new repository root.
2. `hacs.json` here is already plugin-flavored (`name`, `render_readme`).
3. HACS serves `watersmart-card.js` from the repo root; tag releases and add
   the repo to HACS as a _Lovelace_ plugin.

[integration-repo]: https://github.com/wbyoung/watersmart
