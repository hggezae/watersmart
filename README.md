# WaterSmart for Home Assistant

[![HACS](https://img.shields.io/badge/default-grey?logo=homeassistantcommunitystore&logoColor=white)][hacs-repo]
[![HACS installs](https://img.shields.io/github/downloads/wbyoung/watersmart/latest/total?label=installs&color=blue)][hacs-repo]
[![Version](https://img.shields.io/github/v/release/wbyoung/watersmart)][releases]
![Downloads](https://img.shields.io/github/downloads/wbyoung/watersmart/total)
![Build](https://img.shields.io/github/actions/workflow/status/wbyoung/watersmart/pytest.yml
)

This integration pulls data from water utilities that use [WaterSmart by VertexOne][vertexone].
It scrapes data from the web interface and provides a few [sensors](#sensors) with that data.

_Note: data will not be updated frequenly because the water utilities do not always update
this data continuously._

## Installation

### HACS

Installation through [HACS][hacs] is the preferred installation method.

[![Open the WaterSmart integration in HACS][hacs-badge]][hacs-open]

1. Click the button above or go to HACS &rarr; Integrations &rarr; search for
   "WaterSmart" &rarr; select it.
1. Press _DOWNLOAD_.
1. Select the version (it will auto select the latest) &rarr; press _DOWNLOAD_.
1. Restart Home Assistant then continue to [the setup section](#setup).

### Manual Download

1. Go to the [release page][releases] and download the `watersmart.zip` attached
   to the latest release.
1. Unpack the zip file and move `custom_components/watersmart` to the following
   directory of your Home Assistant configuration: `/config/custom_components/`.
1. Restart Home Assistant then continue to [the setup section](#setup).

## Setup

Open your Home Assistant instance and start setting up by following these steps:

1. Navigate to "Settings" &rarr; "Devices & Services"
1. Click "+ Add Integration"
1. Search for and select &rarr; "WaterSmart"

Or you can use the My Home Assistant Button below.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)][config-flow-start]

Follow the instructions to configure the integration.

### Configuration Settings

* _Host_: The subdomain used to access your water utility information. For instance
  `bendoregon`  for `https://bendoregon.watersmart.com/`.
* _Username_: Your email address used to log in.
* _Password_: Your password used to log in.

## Sensors

### `sensor.watersmart_<host>_most_recent_full_day_usage`

Gallons of water used on the most recent full day of data available.

#### Attributes

* `related`: List of related objects with `start` and `gallons` covering the day of data.


### `sensor.watersmart_<host>_most_recent_hour_usage`

Gallons of water used on the most recent hour of data available.

#### Attributes

* `start`: The start of the hour of water usage
* `related`: List of related objects with `start` and `gallons` starting from the most recent
  hour.

### `binary_sensor.watersmart_<host>_leak_detected`

Turns on when WaterSmart's leak data flags hours within the last day, or when
usage runs continuously for at least 6 hours (a common sign of a running
toilet or stuck valve).

#### Attributes

* `lookback_hours`: The window considered for utility-flagged leaks.
* `continuous_flow_threshold_hours`: Hours of uninterrupted usage that trigger detection.
* `continuous_flow_hours`: Longest recent run of uninterrupted usage.
* `leak_gallons`: Utility-reported leak gallons within the lookback window.
* `flagged`: List of flagged records with `start`, `gallons`, and `leak_gallons`.

## Re-authenticating & reconfiguring

If the stored password stops working (for example after rotating it on your
utility's portal), Home Assistant prompts you to re-authenticate from the
WaterSmart integration page. Use _Reconfigure_ to change the host or username
without deleting and re-adding the entry.

## Energy dashboard

The integration imports the hourly water-usage series into Home Assistant's
long-term statistics, making it available to the [Energy dashboard's water
consumption section][energy-water].

Home Assistant stores a consumption series as a running total: every hourly row
holds both that hour's usage and the cumulative total of all the hours before
it. WaterSmart reports each hour on its own, so the integration accumulates the
hourly values into that running total before recording them.

On first run it imports the entire history WaterSmart exposes for the account,
accumulating from zero. Later refreshes do not recompute the whole total.
Instead they find the most recent hour already recorded that is old enough to
have settled — roughly two days back, since WaterSmart keeps revising more
recent hours — and resume accumulating from that hour's running total,
re-importing every hour after it. Revisions WaterSmart has made inside that
window are picked up; older rows are left untouched.

The statistic appears in the Energy dashboard's water-source picker labeled
`Water consumption (<host>)`. Its `statistic_id` is derived from the config
entry's internal id (`watersmart:<entry_id>`) rather than from the host or
username, so re-authenticating or editing either one keeps writing to the same
series instead of stranding it and starting a new one.

### Known limitations

- Historical corrections that WaterSmart emits more than roughly two days after
  the fact are not picked up automatically. If this matters for a particular
  account, removing and re-adding the config entry triggers a fresh full
  backfill.

## Dashboards & visualization

### Finding your statistic id

The hourly series this integration imports is registered under the statistic
id `watersmart:<config_entry_id>`. Find yours under _Developer Tools_ →
_Statistics_ (search for "watersmart"), or from the config entry's URL in
_Settings_ → _Devices & Services_ → _WaterSmart_.

### Hourly & daily graphs with the built-in statistics card

The series is stored as a running total, so chart `change` to see consumption
per period instead of a growing staircase:

```yaml
type: statistics
title: Water usage (hourly)
chart_type: bar
stat_types:
  - change
period: hour
days_to_show: 7
entities:
  - watersmart:YOUR_ENTRY_ID
```

```yaml
type: statistics
title: Water usage (daily)
chart_type: bar
stat_types:
  - change
period: day
days_to_show: 90
entities:
  - watersmart:YOUR_ENTRY_ID
```

The same series powers the Energy dashboard's water section — see
[Energy dashboard](#energy-dashboard).

### WaterSmart Card

The [`lovelace-watersmart/`](lovelace-watersmart/) folder ships a companion
Lovelace card: hourly bars with utility-reported **leak hours highlighted in
red** and a GitHub-contribution-style daily heatmap. See its
[README](lovelace-watersmart/README.md) for installation.

```yaml
type: custom:watersmart-card
title: Water usage
hours: 48
weeks: 12
```

### mini-graph-card on the sensors

For a quick state-based graph of the integration's sensors (no statistics
involved, so history is limited by your recorder's purge settings):

```yaml
type: custom:mini-graph-card
name: Recent hourly usage
entities:
  - sensor.watersmart_yourhost_most_recent_hour_usage
hours_to_show: 48
points_per_hour: 1
```

## Services

### `watersmart.get_hourly_history`

Fetches hourly water usage. The `config_entry` value be found using the _Services_ tab in the _Developer Tools_, selecting the desired entity and then switching to YAML.

#### Service Data Attributes

* `config_entry`: **required** Config entry to use. Example: `1b4a46c6cba0677bbfb5a8c53e8618b0`.
* `cached`: Accept data from the integration cache instead of re-fetching. Defaults to `false`.
* `start`: Start time to history. Example: `2024-06-19T19:30:00-07:00`.
* `end`: End time to history. Example: `2024-06-19T21:30:00-07:00`.


## Credits

Icon designed by [bsd studio][bsd-attribution].

[bsd-attribution]: https://thenounproject.com/creator/nesterenko.ruslan
[config-flow-start]: https://my.home-assistant.io/redirect/config_flow_start/?domain=watersmart
[energy-water]: https://www.home-assistant.io/docs/energy/water/
[hacs]: https://hacs.xyz/
[hacs-repo]: https://github.com/hacs/integration
[hacs-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-open]: https://my.home-assistant.io/redirect/hacs_repository/?owner=wbyoung&repository=watersmart&category=integration
[releases]: https://github.com/wbyoung/watersmart/releases
[vertexone]: https://www.vertexone.net/
