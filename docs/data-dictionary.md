# DustWatch data dictionary

| Model | Purpose | Important fields |
| --- | --- | --- |
| `dustwatch.site` | Solar installation, map location, and current performance state | customer, latitude, longitude, capacity, price, cleaning cost, running loss, status, dust rate |
| `dustwatch.reading` | One daily production record per site | date, sun hours, actual output, expected output, loss, money lost |
| `dustwatch.cleaning.job` | Manager decision, crew work, and outcome | state, recommendation snapshot, cost, recovery, payback |
| `dustwatch.simulator` | Temporary clean-now versus wait calculation | site, wait days, two cycle costs, verdict |

`res.partner` and `crm.lead` are extended with smart buttons that open the same solar-site records from Contacts or CRM.
