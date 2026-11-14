# ADR 0001 Core module boundary

**Status:** Accepted

## Decision

DustWatch is one Odoo module depending on Base, Web, Discuss, Contacts, CRM, and Website. CRM and Contacts provide customer ownership and opportunity entry; Website holds the optional Maps API key used by the fleet map.

## Reason

The hackathon build needs to install on Odoo Community without Project, Accounting, or Portal. The map reads site coordinates from Odoo and uses the Website-configured Google Maps key when available; a built-in coordinate map works without that key. Cleaning jobs carry their own decision and recovery context, so they are stored as `dustwatch.cleaning.job` records instead of Project tasks.

## Consequences

Future invoicing, weather forecasts, and Project connections should be separate bridge modules. The core recommendation engine remains reusable for companies that already have another system and for companies that depend on DustWatch directly.
