# DustWatch product requirements

## Purpose

DustWatch helps solar maintenance companies decide which panels to clean first. It converts lower-than-expected production into kWh and AED losses, ranks sites by urgency, and keeps the decision with an operations manager.

## Version 1 scope

- Solar sites linked to Odoo Contacts.
- Daily output readings imported from monitoring systems or entered manually.
- Per-site expected output, loss, trigger percentage, urgency, and projected due date.
- Manager-approved cleaning jobs with crew assignment.
- Recovery and payback measurement after a clean.
- Fleet priority, job board, results reporting, simulator, and output chart.
- Interactive live map with geolocated site nodes and the same history as CRM and DustWatch menus.
- Black, white, and orange control-room styling based on the Tipsy Taxi admin dashboard.

## Acceptance criteria

1. DustWatch creates an automatic job only in **Recommended** state.
2. A manager accepts or dismisses the recommendation before any crew is scheduled.
3. A crew member can mark a scheduled job complete.
4. Three readings after a completed clean produce a permanent recovery result and payback calculation.
5. A suspected technical fault blocks further recommendations until inspected.
6. The module operates without Project, Accounting, Portal, external weather APIs, or Enterprise features.
7. A map node opens the matching site and shows its reading and cleaning-job history; map and list menus use the same Odoo records.
8. A CRM opportunity's map button scopes the map to its commercial customer.
