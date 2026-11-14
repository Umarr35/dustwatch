# DustWatch

DustWatch is an Odoo 19 Community add-on for solar maintenance teams in Dubai. It calculates each site's loss from soiling, recommends cleaning when the money lost reaches the cleaning cost, lets an operations manager schedule work, and measures whether a completed clean paid off. Odoo CRM is the sales front end: opportunities use the customer contact, and **Live map** shows the same site records used by Fleet priority, Readings, and Cleaning jobs.

## Install

1. Ensure `workshop/Workshop` is in Odoo's `addons_path` so it discovers this add-on.
2. Create a UAE company so AED is the company currency.
3. Update the Apps list and install **DustWatch**. CRM and Website install as dependencies.
4. Give operations staff the **DustWatch / Manager** role and field staff the **DustWatch / Crew** role.
5. For a street map, enter a Google Maps API key in **Website → Configuration → Settings**. Without a key, the live coordinate map remains available.

## Daily operation

1. Manage leads and opportunities in Odoo CRM; link them to the customer contact.
2. Create the customer's solar site in DustWatch and enter its latitude and longitude. The CRM opportunity's **Live map** button opens the customer's map.
3. Open **Live map** to view site status, click a node, and review that site's complete readings and cleaning-job history.
4. Import readings with **Site**, **Date**, **Sun hours**, and **Actual output (kWh)**. The map refreshes from Odoo records every 15 seconds.
5. Open Fleet priority to see the same sites ranked by urgency and daily loss.
6. Review a recommendation, use **Clean now vs wait**, then accept or dismiss it.
7. Assign a crew and mark the scheduled job done.
8. After three readings, open the job to view recovery and payback.

The module includes three Dubai-style sample sites with historic readings and cleaning jobs for a first-run walkthrough.

See the project [documentation](docs/) for the product scope, design, calculation rules, test plan, and integration contract.
