# DustWatch data dictionary

| Model | Purpose | Important fields |
| --- | --- | --- |
| `dustwatch.site` | Solar installation, map location, and current performance state | customer, latitude, longitude, capacity, price, cleaning cost, running loss, status, dust rate |
| `dustwatch.reading` | One daily production record per site | date, sun hours, actual output, expected output, loss, money lost |
| `dustwatch.cleaning.job` | Manager decision, crew work, and outcome | state, recommendation snapshot, cost, recovery, payback |
| `dustwatch.simulator` | Temporary clean-now versus wait calculation | site, wait days, two cycle costs, verdict |
| `dustwatch.weather.forecast` | Issued forecast snapshots for a solar site and day | provider, issued time, rain chance / amount, humidity, dew-risk hours, wind, peak-sun-hours, planned kWh |
| `dustwatch.weather.signal` | Anonymized regional output anomaly correlated with forecast conditions | coarse region cell, event category, site/customer counts, mean shortfall, forecast alignment |
| `dustwatch.weather.settings` | Temporary manager form that saves provider and opt-in settings | provider mode, weather enabled, peer-signal opt-in |

`res.partner` and `crm.lead` are extended with smart buttons that open the same solar-site records from Contacts or CRM.

`dustwatch.reading.weather_forecast_id` links a reading to the latest forecast issued before that Dubai day began. The related planned-output fields are retained for actual-versus-forecast comparison. Regional signals deliberately have no relation to individual sites, readings, partners, or companies.
