# DustWatch test plan

## Automated checks

The `dustwatch/tests` suite covers expected output, loss calculations, recommendation creation, job acceptance, completion, recovery, and the simulator.

The map additions also check coordinate validation and CRM map-action scoping. In the browser, verify that the DustWatch app tab opens the fleet map, the duplicate Live map submenu is absent, and the map page scrolls through the entire dashboard on desktop and mobile. Check that the zinc-black surfaces, amber navigation and action states, white primary text, and muted gray secondary text remain readable on Fleet priority, Readings, Cleaning jobs, Reporting, CRM forms, and record forms. Verify that CRM buttons, map nodes, site forms, readings, and cleaning jobs all navigate to the same site IDs. Confirm the selected node's log includes the full reading and cleaning history and the map refreshes after a new reading is imported. With a Website Google Maps API key configured, confirm Google street tiles and markers load; without a key, verify the coordinate map and Website settings link remain available.

## Demo checks

1. Create a 500 kWp site at AED 0.40 per kWh with a AED 1,500 cleaning cost.
2. Import daily readings that steadily decline.
3. Confirm Fleet priority moves the site from green to amber to red.
4. Confirm one recommended job appears when running loss crosses AED 1,500.
5. Use the simulator to demonstrate both **Wait** and **Clean now** outcomes.
6. Accept the recommendation, assign a crew, and mark it done.
7. Import three improved readings and confirm recovery and payback.
8. Repeat with no improvement and confirm the inspection flag blocks another recommendation.
