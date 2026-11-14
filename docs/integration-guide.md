# DustWatch integration guide

## Readings import contract

Use Odoo's standard import in **DustWatch > Readings**. The required source fields are:

| Incoming field | DustWatch field |
| --- | --- |
| Site identifier or name | `site_id` |
| Reading date | `date` |
| Full-strength sun hours | `sun_hours` |
| Measured energy in kWh | `actual_kwh` |
| Site latitude | `latitude` on `dustwatch.site` |
| Site longitude | `longitude` on `dustwatch.site` |

There can be one reading per site and date. A failed duplicate import is rejected without changing the running loss.

## Connecting another system

An inverter platform can export the four import fields above as CSV and hand it to the operations team. A later integration can create `dustwatch.reading` records through Odoo's XML-RPC or JSON-2 APIs. Keep site configuration in DustWatch so price, cleaning cost, and performance factor remain consistent across imports.

## Odoo CRM front end

Use Odoo CRM for leads and opportunities, with the standard `partner_id` customer contact. Create solar sites against that customer's company contact in DustWatch. On CRM records linked to a customer with sites, the **Solar sites** and **Live map** smart buttons open the matching fleet or customer-filtered map. The map's markers, Fleet priority, and site form all use the same site IDs. Assign the DustWatch Crew or Manager role to users who need those buttons and their related site permissions.

The live map polls Odoo records every 15 seconds. Configure a Google Maps API key in Odoo Website settings to show the street map; without a key, the built-in Dubai coordinate map still supports clickable site nodes and history.

## Weather roadmap

Version 1 accepts sun hours with each reading. A weather service can later supply sun hours and dust-storm risk, but it should feed the same reading import contract rather than duplicate the performance calculation.
