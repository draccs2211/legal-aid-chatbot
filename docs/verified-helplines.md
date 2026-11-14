# Helpline registry

Numbers used by the safety path (`backend/safety.py`). A number appears in
code only if it is listed as **verified** here. Last checked: 2026-11-04.

## Verified (used in static emergency and self-harm messages)

| Number | Service | Source |
|---|---|---|
| 112 | All emergency services (police, fire, ambulance) | UP district NIC page: https://saharanpur.nic.in/?p=2780 |
| 1090 | UP Women Power Line | UP Police: https://uppolice.gov.in/article/en/other-helpful-options |
| 1098 | Child Helpline | UP Police page above; UP district NIC page above |
| 181 | UP Women Helpline (24x7) | News report: https://www.freepressjournal.in/uttar-pradesh/ups-181-women-helpline-assists-over-842-lakh-women-since-2017-emerges-as-key-safety-support-system (news source, not a government page: re-check when possible) |
| 14416 | Tele-MANAS national mental-health helpline, free, 24x7 (also 1-800-89-14416) | https://jipmer.edu.in/Tele-MANAS (cites a Health Ministry letter) and https://en.vikaspedia.in/viewcontent/health/mental-health/national-tele-mental-health-programme |

## Listed in config but NOT yet verified (do not add to static messages)

14566 (SC/ST), 1930 (cyber crime), 15100 (free legal aid), 1915 (consumer),
EPFO 1800-118-005, and the landline numbers in `DOMAIN_HELPLINES`
(UP Information Commission, UPSLSA, UP SC/ST Commission, revenue helpline).
1076 (UP CM helpline) appears on the UP district page above but is not used
in the safety path.

Removed from the emergency block in Task 3 until verified: 14566, 1076.
