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

The map also draws an estimated weather-coverage range around each geolocated solar site. Nearby sites are connected into clusters when each link is within 8 km; the map shows each site's range plus the connected cluster footprint. For the current Open-Meteo setup the range uses a rough 10 km model-scale assumption, with a wider 20 km range for isolated sites. The support indicator increases with nearby sites and is a transparent heuristic, not a provider confidence value or validated accuracy percentage. The map represents a `dustwatch.site` installation/system; individual panel-level ranges require individual panel coordinates and readings.

## Weather forecasts and solar output plans

Weather integration is disabled by default. A DustWatch manager opens **DustWatch → Configuration → Weather settings**, chooses the provider plan, enables weather, then uses **Save and refresh now**. The provider receives site latitude and longitude only after this setting is enabled. Public preview is for non-commercial evaluation; use the commercial Open-Meteo endpoint and its API key for commercial deployment. The key is stored in Odoo's system parameters, not in the add-on source.

DustWatch requests daily weather code, precipitation amount / probability, shortwave solar radiation, maximum wind, and hourly humidity, dew point, and temperature. Forecast data is retained as issued snapshots. Shortwave radiation in MJ/m² is divided by 3.6 to obtain equivalent peak-sun-hours; planned kWh is `capacity_kwp × peak_sun_hours × performance_factor`. This is a coarse horizontal-radiation estimate and does not account for panel tilt, azimuth, shading, inverter clipping, or site-specific soiling.

Google Maps Platform Weather API is a viable alternative or supplement for current conditions, precipitation, humidity, wind, and hourly/daily forecasts in the UAE. It has global location coverage with forecast detail described by Google as a few kilometers, but standard Weather API use requires a billed Google Cloud project and has per-request pricing after its monthly free usage cap. The existing Google Maps key does not enable the Weather API automatically. Keep Open-Meteo as the current output-planning source because this implementation uses its shortwave-radiation field; Google can be added for localized weather conditions after a provider adapter and separate server-side key are configured. Do not infer solar generation from weather conditions alone.

Rain and damp-weather rules are deliberately advisory. A forecast of at least 4 mm with a 70% or greater rain probability suggests reviewing crew timing and inspecting after rain; it does not assume rain will wash panels. Three or more humid / near-dewpoint hours can add a moisture-risk note. Neither signal creates or cancels a cleaning job or replaces the loss-to-clean-cost trigger.

Each reading links to the latest stored forecast issued before the start of that Dubai date. The reading view reports planned output, actual-minus-plan variance, and signed variance percentage. This makes weather-plan error reviewable without changing the existing soiling-loss calculation.

## Cross-customer regional signals

This feature is disabled by default and requires a manager to opt in under Weather settings. The daily job looks for at least three same-day site shortfalls across at least two distinct customer contacts in a coarse 0.5-degree grid cell. It classifies possible dry/windy dust conditions, rain/storm context, or an unclassified output anomaly, then stores only aggregate counts and mean values. It does not store site/customer names or exact coordinates in the signal model. Treat it as an experimental correlation indicator, not a meteorological prediction; test with sufficient participating sites before using it for operational decisions.

Open-Meteo's public endpoint is restricted to non-commercial use; its commercial service uses a separate endpoint and API key. Weather data requires CC BY 4.0 attribution, shown in the live-map weather panel and forecast views. See [Open-Meteo pricing and licensing](https://open-meteo.com/en/pricing).

Google Weather API references: [overview](https://developers.google.com/maps/documentation/weather/overview), [coverage and resolution FAQ](https://developers.google.com/maps/documentation/weather/faq), and [usage and billing](https://developers.google.com/maps/documentation/weather/usage-and-billing).

## Weather roadmap

Version 1 accepts sun hours with each reading. A weather service can later supply sun hours and dust-storm risk, but it should feed the same reading import contract rather than duplicate the performance calculation.
