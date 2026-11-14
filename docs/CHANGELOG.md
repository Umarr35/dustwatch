# Change log

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
