# -*- coding: utf-8 -*-
from datetime import datetime, time

import pytz


DUBAI_TZ = pytz.timezone('Asia/Dubai')


def dubai_day_start_utc(day):
    """Return midnight at the start of a Dubai date as Odoo's naive UTC."""
    local_midnight = DUBAI_TZ.localize(datetime.combine(day, time.min))
    return local_midnight.astimezone(pytz.UTC).replace(tzinfo=None)
