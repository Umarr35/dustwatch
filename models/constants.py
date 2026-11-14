# -*- coding: utf-8 -*-
"""Every tunable number of DustWatch lives here and nowhere else (ARC-04).

To change how the app behaves (when a clean is recommended, how long a
dismissal snoozes a site, how many readings a window holds...) change the
value in this file only. No other file types a threshold.
"""

# ---------------------------------------------------------------------------
# Section 5.1 of the specification: calculation constants
# ---------------------------------------------------------------------------
TRIGGER_PCT = 100.0             # recommend a clean when trigger_pct reaches this
AMBER_PCT = 70.0                # status turns amber at this trigger_pct
RECENT_WINDOW = 3               # readings used for current loss and loss per day
RECOVERY_WINDOW = 3             # readings before and after a clean used to measure recovery
FAULT_MAX_RECOVERY_PCT = 50.0   # recovery below this suggests a fault
FAULT_MIN_LOSS_PCT = 3.0        # the fault check applies only when loss before the clean was at least this
SNOOZE_DAYS = 7                 # days without a new recommendation after a dismissal
DEFAULT_WAIT_DAYS = 7           # the simulator's wait and the snapshot's wait cost
DEFAULT_DUST_RATE_PCT = 0.20    # dust rate used when a site has too little data
MIN_DAYS_FOR_DUST_RATE = 7      # days since clean needed before the site's own dust rate is used
REFERENCE_WINDOW = 7            # readings averaged for the reference expected output
DEFAULT_SUN_HOURS = 5.5         # sun hours assumed for a site with no reading
MAX_PROJECTION_DAYS = 365       # upper limit for days_to_trigger
CHART_MAX_POINTS = 120          # readings shown on the output chart

# ---------------------------------------------------------------------------
# Section 4 of the specification: field defaults and allowed ranges
# ---------------------------------------------------------------------------
DEFAULT_PRICE_PER_KWH = 0.40        # AED per kWh, default of a new site
DEFAULT_PERFORMANCE_FACTOR = 0.80   # share of rated power reaching the meter
MAX_PERFORMANCE_FACTOR = 1.0        # performance factor: above 0, at most this
MAX_SUN_HOURS = 14.0                # sun hours of a reading: from 0 to this
MIN_WAIT_DAYS = 1                   # simulator "Days to wait": from this...
MAX_WAIT_DAYS = 60                  # ...to this
MAX_LOSS_PCT = 100.0                # a projected loss can never exceed 100 %

# ---------------------------------------------------------------------------
# Section 5.5 (CAL-18): decimals kept when a value is stored.
# Formulas work on unrounded values; thresholds compare the stored values.
# ---------------------------------------------------------------------------
MONEY_DIGITS = 2        # AED amounts
KWH_DIGITS = 2          # energy and sun hours
PCT_DIGITS = 2          # percentage points (4.0 means 4 %)
DUST_RATE_DIGITS = 3    # dust rate, % per day
PRICE_DIGITS = 4        # AED per kWh
FACTOR_DIGITS = 3       # performance factor (the only fraction: 0.80 = 80 %)
ONE_DECIMAL = 1         # recovery % and payback days

# ---------------------------------------------------------------------------
# Selection keys shared by several models (section 4)
# ---------------------------------------------------------------------------
SITE_STATUS = [
    ('green', 'On track'),
    ('amber', 'Approaching'),
    ('red', 'Clean due'),
]
# urgency_sequence for each status: 1 = most urgent (CAL-07, D7)
URGENCY_BY_STATUS = {'red': 1, 'amber': 2, 'green': 3}

JOB_STATES = [
    ('recommended', 'Recommended'),
    ('scheduled', 'Scheduled'),
    ('done', 'Done'),
    ('dismissed', 'Dismissed'),
]
# A job in one of these states is "open": a site has at most one (DM-J-03).
OPEN_JOB_STATES = ('recommended', 'scheduled')
# Columns always shown on the cleaning jobs board, in this order (DM-J-04).
BOARD_JOB_STATES = ('recommended', 'scheduled', 'done')

JOB_ORIGINS = [
    ('auto', 'DustWatch recommendation'),
    ('manual', 'Requested by user'),
]

RECOVERY_STATES = [
    ('pending', 'Awaiting readings'),
    ('confirmed', 'Recovery confirmed'),
    ('fault', 'No recovery'),
]

SIMULATOR_VERDICTS = [
    ('clean_now', 'Clean now'),
    ('wait', 'Wait'),
]

# ---------------------------------------------------------------------------
# Fixed texts used in more than one place
# ---------------------------------------------------------------------------
MANAGER_GROUP = 'dustwatch.group_dustwatch_manager'
TODO_ACTIVITY_TYPE = 'mail.mail_activity_data_todo'
NOTE_SUBTYPE = 'mail.mt_note'
REVIEW_SUMMARY = 'Review cleaning recommendation'    # FR-REC-03
INSPECTION_SUMMARY = 'Technical inspection'          # WF-06, FR-FAU-03
