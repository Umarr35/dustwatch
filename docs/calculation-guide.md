# DustWatch calculation guide

All monetary values are AED. Percentages ending in `_pct` use percentage points: `4.0` means 4%.

| Result | Formula |
| --- | --- |
| Expected output | capacity kWp × sun hours × performance factor |
| Daily lost kWh | max(expected output − actual output, 0) |
| Daily loss AED | lost kWh × electricity price |
| Running loss | daily AED loss after the last clean |
| Trigger percentage | running loss ÷ cleaning cost × 100 |
| Status | Green below 70%, amber from 70%, red from 100% |
| Dust rate | current loss percentage ÷ mean day number in the recent window |
| Recovery | loss before clean − loss after clean |
| Payback days | cleaning cost ÷ recovered AED per day |

The simulator compares the total cost per day for cleaning now versus waiting. It does not simply compare the next seven days, since both options eventually include one clean.
