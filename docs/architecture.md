# DustWatch architecture

```mermaid
flowchart LR
  R[Daily readings] --> E[Odoo calculation engine]
  E --> S[Solar site metrics]
  S --> D{Loss reaches cleaning cost?}
  D -->|Yes| J[Recommended cleaning job]
  J --> M[Manager review]
  M -->|Accept| C[Crew cleaning]
  C --> A[Three follow-up readings]
  A --> P[Recovery and payback]
  CRM[Odoo CRM opportunity] --> K[Customer contact]
  K --> S
  S --> MAP[Live map client action]
  MAP -->|node click| S
  MAP -->|site history| R
  WX[Weather provider] --> WF[Issued daily forecast snapshots]
  S --> WF
  WF --> WA[Rain and damp-weather advisory]
  WF --> OP[Weather-based output plan]
  OP -->|forecast captured before day| R
  R -->|opt-in, coarse region only| PEER[Cross-customer anomaly signal]
  WF -->|official forecast context| PEER
```

The `dustwatch` module depends on Odoo Base, Web, Discuss, Contacts, CRM, and Website. CRM leads and opportunities remain the sales front end and use Odoo customer contacts. A CRM Live map button resolves the opportunity to its commercial partner. The Live map client action reads the same `dustwatch.site`, `dustwatch.reading`, and `dustwatch.cleaning.job` records as Fleet priority and the site form. Selecting a node loads that site's full reading and cleaning history; opening a record returns to the canonical Odoo form. Site coordinates are stored on `dustwatch.site`, and the map refreshes from Odoo every 15 seconds. Odoo Website's configured Maps API key enables street tiles; a coordinate map remains available without the key. The `dustwatch.simulator` transient model is used only while the comparison dialog is open.

The engine recalculates stored site fields when readings or site settings change. This keeps the fleet list fast and ensures that list sorting uses stored values.

Weather is opt-in and runs in scheduled Odoo jobs. `dustwatch.weather.forecast` keeps issued forecast snapshots so readings can link to the version available before the Dubai day began. Daily shortwave radiation is converted from MJ/m² to equivalent peak-sun-hours, then multiplied by site capacity and performance factor. This is a planning estimate, not a panel-tilt or inverter simulation. Rain and humidity only add an explainable timing advisory; they do not override the economic cleaning trigger or schedule a job.

Cross-customer analysis is disabled by default. With manager opt-in, a daily job evaluates same-day output shortfalls against stored weather plans. It only persists a coarse-region aggregate after at least three sites from at least two customer contacts agree. No source site IDs, customer names, company IDs, or precise coordinates are stored in a signal. The heuristic is an early-warning experiment, not a trained weather model or an official storm forecast.
