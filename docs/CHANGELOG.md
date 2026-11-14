# Change log

## Weather forecast update - 2026-11-14

- Added opt-in Open-Meteo forecasts for Dubai rain, humidity / dew risk, wind, weather codes, and solar radiation.
- Added low-priority cleaning timing advice that never auto-books or cancels a job and leaves the financial trigger authoritative.
- Added day-ahead peak-sun-hour and output plans, linked readings to the forecast available before the Dubai day, and exposed actual-versus-plan variance.
- Added an opt-in anonymized cross-customer regional anomaly signal requiring at least three sites and two customers; no customer/site identifiers are stored in signal rows.
- Added manager-only provider settings, commercial endpoint support, six-hour refresh, daily signal analysis, and forecast-history cleanup.
- Verified Odoo module loading and weather-disabled startup; no external forecast requests are made until a manager enables the provider.

## DustWatch contrast and navbar update - 2026-11-14

- Reworked Odoo navbar colors to use the Tipsy Taxi zinc-black and amber palette instead of Odoo's purple brand color.
- Forced readable light foregrounds for inherited dark text classes on DustWatch's charcoal panels, with muted gray secondary text.
- Matched primary buttons, selected tabs, dropdowns, and popovers to the Tipsy Taxi admin dashboard styling.

## DustWatch usability update - 2026-11-14

- Made the DustWatch app tab open its live fleet map and removed the duplicate Live map submenu.
- Fixed the map dashboard scroll container so its full contents remain reachable on desktop and mobile.
- Applied the charcoal, orange, and white theme to fleet, readings, cleaning, reporting, and record views.
- Added a direct Website settings link when the Google Maps API key is missing; the interactive coordinate map remains usable without it.
- Verified the Odoo module upgrade and all 17 DustWatch tests pass; the Odoo server is running locally on port 8070.

## Live map update - 2026-11-14

- Added site coordinates, input validation, and a safe coordinate backfill for the existing demo records.
- Added an Odoo Live map client action with a Website-configured Google map and interactive Dubai coordinate fallback.
- Added 15-second Odoo-data refresh, searchable status filters, selectable site nodes, and full reading/cleaning history.
- Added CRM opportunity map entry and canonical links to the existing Fleet, Readings, Cleaning jobs, and site form records.
- Applied the black, white, and orange control-room styling from the Tipsy Taxi admin dashboard.
- Verified all 17 DustWatch tests pass.

## Integration update - 2026-11-14

- Synced the Odoo 19 add-on from `updated-duskwatch/main` at `39c2530`.
- Added Odoo CRM as the sales front end and a customer-to-fleet smart button.
- Loaded sample Dubai sites, historical cleaning jobs, and daily readings.
- Set the local DustWatch company currency to AED for the demo.
- Verified all 15 DustWatch tests pass at that integration point.

## 19.0.1.0.0 - 2026-11-13

- Added DustWatch Odoo 19 CRM module.
- Added solar sites, readings, cleaning jobs, and simulator.
- Added loss, prediction, recommendation, recovery, and payback calculations.
- Added Manager and Crew roles, fleet and job screens, reporting, import-ready readings, and output chart.
