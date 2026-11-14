# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare, float_is_zero, float_round

from . import constants as const

# English month names for texts such as "30 Sep 2026" (FR-EXP-02). Written
# out here so the result never depends on the server's locale.
_MONTH_ABBR = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


class DustwatchSite(models.Model):
    """A solar rooftop (specification section 4.1).

    The site is the hub of the app: readings and cleaning jobs each belong to
    one site, and every dust metric shown on screen is stored on the site.
    """
    _name = 'dustwatch.site'
    _description = 'Solar Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']   # DM-S-01
    # DM-S-02 / D7: colour first (red, amber, green), then the site losing
    # the most money per day. All three fields are stored, so the fleet list
    # is sorted by the database (NFR-05).
    _order = 'urgency_sequence, avg_daily_loss desc, id'

    # ------------------------------------------------------------------
    # Settings, entered by a manager
    # ------------------------------------------------------------------
    name = fields.Char(string='Site', required=True)
    active = fields.Boolean(string='Active', default=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True,
        ondelete='restrict',   # deleting the contact is blocked while sites exist
    )
    manager_id = fields.Many2one(
        'res.users', string='Operations manager', required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',   # receives the site's activities
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='company_id.currency_id', store=True, readonly=True,
    )
    capacity_kwp = fields.Float(
        string='Capacity (kWp)', digits=(16, const.KWH_DIGITS), required=True,
    )
    price_per_kwh = fields.Float(
        string='Electricity price (AED/kWh)', digits=(16, const.PRICE_DIGITS),
        required=True, default=const.DEFAULT_PRICE_PER_KWH,
    )
    cleaning_cost = fields.Monetary(string='Cost of one clean', required=True)
    performance_factor = fields.Float(
        string='Performance factor', digits=(16, const.FACTOR_DIGITS),
        required=True, default=const.DEFAULT_PERFORMANCE_FACTOR,
    )
    # Changed by "Mark done" on a job (WF-05) or by a manager's edit.
    last_cleaned_date = fields.Date(
        string='Last cleaned', required=True, default=fields.Date.context_today,
    )
    # Set by the fault check (CAL-16), cleared by "Mark inspected" (WF-07).
    fault_suspected = fields.Boolean(string='Inspection needed', default=False)
    notes = fields.Text(string='Notes')
    latitude = fields.Float(string='Latitude', digits=(16, 6))
    longitude = fields.Float(string='Longitude', digits=(16, 6))
    weather_last_fetch_at = fields.Datetime(string='Last weather refresh', readonly=True)
    weather_last_error = fields.Char(string='Weather refresh status', readonly=True)

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    reading_ids = fields.One2many('dustwatch.reading', 'site_id', string='Readings')
    job_ids = fields.One2many('dustwatch.cleaning.job', 'site_id', string='Cleaning jobs')
    weather_forecast_ids = fields.One2many(
        'dustwatch.weather.forecast', 'site_id', string='Weather forecasts',
    )
    # The site's job in state recommended or scheduled, otherwise empty.
    open_job_id = fields.Many2one(
        'dustwatch.cleaning.job', string='Open job',
        compute='_compute_open_job_id', store=True, ondelete='set null',
    )
    # Helper for the site page only: a view cannot look through a link, so
    # the "A clean is recommended" banner needs the open job's state here.
    open_job_state = fields.Selection(
        related='open_job_id.state', string='Open job status',
    )
    # Counters for the smart buttons. The Python labels differ from the
    # one2many labels so Odoo does not log a "same label" warning (NFR-01);
    # the buttons themselves show "Readings" and "Cleaning jobs".
    reading_count = fields.Integer(string='Number of readings', compute='_compute_counts')
    job_count = fields.Integer(string='Number of cleaning jobs', compute='_compute_counts')

    # ------------------------------------------------------------------
    # Next-day weather, exposed as an advisory to the cleaning decision
    # ------------------------------------------------------------------
    weather_next_forecast_id = fields.Many2one(
        'dustwatch.weather.forecast', string='Next-day forecast',
        compute='_compute_weather_summary',
    )
    weather_forecast_date = fields.Date(string='Forecast date', compute='_compute_weather_summary')
    weather_conditions = fields.Char(string='Forecast conditions', compute='_compute_weather_summary')
    weather_precipitation_mm = fields.Float(
        string='Forecast rain (mm)', digits=(16, 2), compute='_compute_weather_summary',
    )
    weather_precipitation_probability = fields.Float(
        string='Rain chance (%)', digits=(16, 1), compute='_compute_weather_summary',
    )
    weather_humidity_max = fields.Float(
        string='Maximum humidity (%)', digits=(16, 1), compute='_compute_weather_summary',
    )
    weather_dew_risk_hours = fields.Float(
        string='Damp / near-dewpoint hours', digits=(16, 1), compute='_compute_weather_summary',
    )
    weather_wind_speed_max = fields.Float(
        string='Maximum wind (km/h)', digits=(16, 1), compute='_compute_weather_summary',
    )
    weather_peak_sun_hours = fields.Float(
        string='Forecast peak-sun hours', digits=(16, 2), compute='_compute_weather_summary',
    )
    weather_expected_kwh = fields.Float(
        string='Weather-based planned output (kWh)', digits=(16, 2),
        compute='_compute_weather_summary',
    )
    weather_provider = fields.Char(string='Weather source', compute='_compute_weather_summary')
    weather_cleaning_advice = fields.Selection([
        ('no_data', 'No forecast'),
        ('follow_financial_trigger', 'Follow financial trigger'),
        ('review_after_rain', 'Review after forecast rain'),
        ('clean_before_damp', 'Consider cleaning before damp weather'),
        ('monitor_moisture', 'Monitor moisture risk'),
    ], string='Weather cleaning advice', compute='_compute_weather_summary')
    weather_advice_reason = fields.Text(string='Weather advice reason', compute='_compute_weather_summary')

    # ------------------------------------------------------------------
    # Dust metrics, stored and read-only: all set by _compute_dust_metrics
    # ------------------------------------------------------------------
    last_reading_date = fields.Date(
        string='Last reading', compute='_compute_dust_metrics', store=True,
    )
    days_since_clean = fields.Integer(
        string='Days since clean', compute='_compute_dust_metrics', store=True,
        aggregator='avg',
    )
    running_loss = fields.Monetary(
        string='Lost since last clean', compute='_compute_dust_metrics', store=True,
    )
    running_loss_kwh = fields.Float(
        string='Lost since last clean (kWh)', digits=(16, const.KWH_DIGITS),
        compute='_compute_dust_metrics', store=True,
    )
    trigger_pct = fields.Float(
        string='% of trigger', digits=(16, const.PCT_DIGITS),
        compute='_compute_dust_metrics', store=True, aggregator='avg',
    )
    status = fields.Selection(
        const.SITE_STATUS, string='Status',
        compute='_compute_dust_metrics', store=True,
    )
    urgency_sequence = fields.Integer(
        string='Urgency', compute='_compute_dust_metrics', store=True,
        aggregator='min',
    )
    current_loss_pct = fields.Float(
        string='Current loss (%)', digits=(16, const.PCT_DIGITS),
        compute='_compute_dust_metrics', store=True, aggregator='avg',
    )
    avg_daily_loss = fields.Monetary(
        string='Losing per day', compute='_compute_dust_metrics', store=True,
    )
    dust_rate_pct = fields.Float(
        string='Dust rate (% per day)', digits=(16, const.DUST_RATE_DIGITS),
        compute='_compute_dust_metrics', store=True, aggregator='avg',
    )
    days_to_trigger = fields.Integer(
        string='Clean due in (days)', compute='_compute_dust_metrics', store=True,
        aggregator='avg',
    )

    # ==================================================================
    # Shared helpers (used by the jobs and the simulator as well)
    # ==================================================================
    @api.model
    def _mean(self, values):
        """Average of a list of numbers, 0 for an empty list (NFR-06)."""
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    @api.model
    def _format_number(self, value, decimals=0):
        """A number as text with thousands separators: 1515.36 -> '1,515'."""
        rounded = float_round(value or 0.0, precision_digits=decimals)
        return '{:,.{decimals}f}'.format(rounded, decimals=decimals)

    @api.model
    def _format_date(self, value):
        """A date as text, like '30 Sep 2026'. Empty text for no date."""
        if not value:
            return ''
        return '%d %s %d' % (value.day, _MONTH_ABBR[value.month - 1], value.year)

    @api.model
    def _backfill_sample_coordinates(self):
        """Give the existing demo rooftops locations when upgrading old DBs.

        The sample site records are noupdate data. Backfill only records that
        still have no coordinates so a manager's later location edits remain
        intact across module upgrades.
        """
        locations = {
            'site_al_noor': (25.2048, 55.2708),
            'site_jebel_ali': (24.9857, 55.0273),
            'site_greenfield': (25.1174, 55.2438),
        }
        for xml_id, (latitude, longitude) in locations.items():
            site = self.env.ref('dustwatch.%s' % xml_id, raise_if_not_found=False)
            if site and not site.latitude and not site.longitude:
                site.write({'latitude': latitude, 'longitude': longitude})
        return True

    @api.model
    def _check_manager_rights(self):
        """Refuse the action unless the user is a DustWatch manager.

        The buttons are already hidden from the crew (SEC-04). This check
        gives the same answer to a direct call. Superuser code, such as the
        scheduled action and the tests, always passes.
        """
        if self.env.su or self.env.user.has_group(const.MANAGER_GROUP):
            return
        raise AccessError(_("Only a DustWatch manager can do this."))

    def _as_of_date(self):
        """The site's as-of date: the date of its latest reading (D3).

        All "now" logic in calculations uses this date, not the clock, so
        results depend only on the data loaded. A site with no reading falls
        back to today (WF-11).
        """
        self.ensure_one()
        return self.last_reading_date or fields.Date.context_today(self)

    # ==================================================================
    # Computed links
    # ==================================================================
    @api.depends('job_ids.state')
    def _compute_open_job_id(self):
        for site in self:
            open_jobs = site.job_ids.filtered(
                lambda job: job.state in const.OPEN_JOB_STATES)
            site.open_job_id = open_jobs[:1]

    @api.depends('reading_ids', 'job_ids')
    def _compute_counts(self):
        for site in self:
            site.reading_count = len(site.reading_ids)
            site.job_count = len(site.job_ids)

    @api.depends(
        'status', 'weather_forecast_ids.forecast_date', 'weather_forecast_ids.issued_at',
        'weather_forecast_ids.weather_code', 'weather_forecast_ids.precipitation_mm',
        'weather_forecast_ids.precipitation_probability', 'weather_forecast_ids.humidity_max',
        'weather_forecast_ids.dew_risk_hours', 'weather_forecast_ids.wind_speed_max',
        'weather_forecast_ids.peak_sun_hours', 'weather_forecast_ids.forecast_expected_kwh',
        'weather_forecast_ids.provider',
    )
    def _compute_weather_summary(self):
        """Expose the next forecast as an advisory, never an automatic job."""
        forecast_date = fields.Date.context_today(self) + timedelta(days=1)
        forecast_records = self.env['dustwatch.weather.forecast'].search([
            ('site_id', 'in', self.ids),
            ('forecast_date', '=', forecast_date),
        ], order='issued_at desc, id desc')
        latest_by_site = {}
        for forecast_record in forecast_records:
            latest_by_site.setdefault(forecast_record.site_id.id, forecast_record)

        for site in self:
            forecast = latest_by_site.get(site.id) or self.env['dustwatch.weather.forecast']

            site.weather_next_forecast_id = forecast
            site.weather_forecast_date = forecast.forecast_date if forecast else False
            site.weather_conditions = forecast.weather_description if forecast else False
            site.weather_precipitation_mm = forecast.precipitation_mm if forecast else 0.0
            site.weather_precipitation_probability = forecast.precipitation_probability if forecast else 0.0
            site.weather_humidity_max = forecast.humidity_max if forecast else 0.0
            site.weather_dew_risk_hours = forecast.dew_risk_hours if forecast else 0.0
            site.weather_wind_speed_max = forecast.wind_speed_max if forecast else 0.0
            site.weather_peak_sun_hours = forecast.peak_sun_hours if forecast else 0.0
            site.weather_expected_kwh = forecast.forecast_expected_kwh if forecast else 0.0
            site.weather_provider = forecast.provider if forecast else False

            if not forecast:
                site.weather_cleaning_advice = 'no_data'
                site.weather_advice_reason = _(
                    'Enable weather forecasts in DustWatch configuration to see a site-specific outlook.'
                )
            elif (
                site.status in ('red', 'amber')
                and forecast.precipitation_probability >= 70.0
                and forecast.precipitation_mm >= 4.0
            ):
                site.weather_cleaning_advice = 'review_after_rain'
                site.weather_advice_reason = _(
                    'At least %(rain)s mm of rain is forecast with a 70%% or higher probability. Review crew timing and inspect after the rain; rain is not assumed to clean panels.',
                    rain='%.1f' % forecast.precipitation_mm,
                )
            elif site.status in ('red', 'amber') and forecast.dew_risk_hours >= 3.0:
                site.weather_cleaning_advice = 'clean_before_damp'
                site.weather_advice_reason = _(
                    'Several humid or near-dewpoint hours are forecast. If cleaning is already economically due, consider scheduling before the damp period; humidity alone does not trigger a clean.'
                )
            elif forecast.dew_risk_hours >= 3.0:
                site.weather_cleaning_advice = 'monitor_moisture'
                site.weather_advice_reason = _(
                    'Damp-weather risk is elevated. Monitor the site; keep the existing loss-to-clean-cost trigger as the cleaning decision.'
                )
            else:
                site.weather_cleaning_advice = 'follow_financial_trigger'
                site.weather_advice_reason = _(
                    'The forecast does not materially change the current loss-to-clean-cost recommendation.'
                )

    # ==================================================================
    # Calculations (specification section 5.2)
    # ==================================================================
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for site in self:
            if not -90 <= site.latitude <= 90:
                raise ValidationError(_('Latitude must be between -90 and 90.'))
            if not -180 <= site.longitude <= 180:
                raise ValidationError(_('Longitude must be between -180 and 180.'))
            if bool(site.latitude) != bool(site.longitude):
                raise ValidationError(_('Enter both latitude and longitude, or leave both blank.'))

    def _cycle_figures(self):
        """CAL-05 to CAL-10 for one site, as unrounded numbers (CAL-18).

        This is the single place where the site formulas are written. It is
        used by _compute_dust_metrics (which stores the results, rounded) and
        by _projected_loss (which must keep working on unrounded values).

        "Current cycle" means the site's readings dated after its
        last_cleaned_date. The "recent window" is the latest 3 readings of
        the current cycle, or fewer if the cycle has fewer.
        """
        self.ensure_one()
        last_cleaned = self.last_cleaned_date
        # Sorted by date in Python, so the result never depends on the order
        # in which readings were imported (FR-READ-07).
        readings = self.reading_ids.filtered('date').sorted('date')
        as_of = readings[-1].date if readings else False

        cycle = readings.browse()
        if last_cleaned:
            cycle = readings.filtered(lambda reading: reading.date > last_cleaned)
        # 0 when the current cycle has no reading.
        days_since_clean = (as_of - last_cleaned).days if cycle else 0

        # CAL-05: sums over the current cycle. Each reading's money lost is
        # already a whole number of fils (stored with 2 decimals).
        running_loss = sum(cycle.mapped('lost_aed'))
        running_loss_kwh = sum(cycle.mapped('lost_kwh'))

        # CAL-06, guarded against a zero cleaning cost (NFR-06).
        trigger_pct = 0.0
        if self.cleaning_cost > 0:
            trigger_pct = running_loss / self.cleaning_cost * 100.0

        # CAL-08 and CAL-09 on the recent window. The loss % is taken
        # unrounded from the reading's own formula.
        recent = cycle[-const.RECENT_WINDOW:]
        current_loss_pct = self._mean(
            reading._loss_values()['loss_pct'] for reading in recent)
        avg_daily_loss = self._mean(recent.mapped('lost_aed'))

        # CAL-10: loss % gained per day since the clean. A reading's day
        # number is the days from last_cleaned_date to its date.
        mean_day_number = self._mean(
            (reading.date - last_cleaned).days for reading in recent)
        dust_rate_pct = 0.0
        if recent and mean_day_number > 0:
            dust_rate_pct = current_loss_pct / mean_day_number
        if (
            days_since_clean < const.MIN_DAYS_FOR_DUST_RATE
            or not recent
            or float_is_zero(dust_rate_pct, precision_digits=const.DUST_RATE_DIGITS)
        ):
            # Too little data to trust the site's own rate.
            dust_rate_pct = const.DEFAULT_DUST_RATE_PCT

        # CAL-11: reference expected output = mean of the latest 7 readings
        # from any cycle; a site with no reading uses its rated output.
        latest = readings[-const.REFERENCE_WINDOW:]
        if latest:
            reference_kwh = self._mean(latest.mapped('expected_kwh'))
        else:
            reference_kwh = (
                self.capacity_kwp * const.DEFAULT_SUN_HOURS * self.performance_factor)

        return {
            'as_of': as_of,
            'days_since_clean': days_since_clean,
            'running_loss': running_loss,
            'running_loss_kwh': running_loss_kwh,
            'trigger_pct': trigger_pct,
            'current_loss_pct': current_loss_pct,
            'avg_daily_loss': avg_daily_loss,
            'dust_rate_pct': dust_rate_pct,
            'reference_kwh': reference_kwh,
        }

    def _projected_cumulative_losses(self, figures, days):
        """CAL-11: projected money lost on each future day, added up.

        Returns a list: item k-1 is the loss summed over future days 1..k,
        counted from the as-of date and assuming no clean. On day k the loss
        is dust rate x (days since clean + k), at most 100 %.
        """
        self.ensure_one()
        cumulative_losses = []
        total = 0.0
        for day_number in range(1, days + 1):
            loss_pct = min(
                figures['dust_rate_pct'] * (figures['days_since_clean'] + day_number),
                const.MAX_LOSS_PCT,
            )
            total += figures['reference_kwh'] * loss_pct / 100.0 * self.price_per_kwh
            cumulative_losses.append(total)
        return cumulative_losses

    def _projected_loss(self, days):
        """CAL-12: AED lost over the next `days` days without a clean."""
        self.ensure_one()
        days = max(int(days or 0), 0)
        cumulative_losses = self._projected_cumulative_losses(self._cycle_figures(), days)
        return cumulative_losses[-1] if cumulative_losses else 0.0

    # DM-S-04: one method sets every dust metric.
    @api.depends(
        'reading_ids.date', 'reading_ids.lost_aed', 'reading_ids.lost_kwh',
        'reading_ids.loss_pct', 'reading_ids.expected_kwh',
        'last_cleaned_date', 'cleaning_cost', 'price_per_kwh',
        'capacity_kwp', 'performance_factor',
    )
    def _compute_dust_metrics(self):
        for site in self:
            figures = site._cycle_figures()

            # CAL-18: threshold checks use the values as they are stored.
            running_loss = float_round(
                figures['running_loss'], precision_digits=const.MONEY_DIGITS)
            trigger_pct = float_round(
                figures['trigger_pct'], precision_digits=const.PCT_DIGITS)

            # CAL-07 / FR-LOSS-02: green below 70 %, amber from 70 %, red from 100 %.
            if float_compare(trigger_pct, const.TRIGGER_PCT,
                             precision_digits=const.PCT_DIGITS) >= 0:
                status = 'red'
            elif float_compare(trigger_pct, const.AMBER_PCT,
                               precision_digits=const.PCT_DIGITS) >= 0:
                status = 'amber'
            else:
                status = 'green'

            # CAL-13: 0 once the running loss has reached the cleaning cost,
            # otherwise the smallest number of days after which it will.
            cleaning_cost = site.cleaning_cost
            if float_compare(running_loss, cleaning_cost,
                             precision_digits=const.MONEY_DIGITS) >= 0:
                days_to_trigger = 0
            else:
                days_to_trigger = const.MAX_PROJECTION_DAYS
                cumulative_losses = site._projected_cumulative_losses(
                    figures, const.MAX_PROJECTION_DAYS)
                for day_number, projected in enumerate(cumulative_losses, start=1):
                    if float_compare(running_loss + projected, cleaning_cost,
                                     precision_digits=const.MONEY_DIGITS) >= 0:
                        days_to_trigger = day_number
                        break

            site.last_reading_date = figures['as_of']
            site.days_since_clean = figures['days_since_clean']
            site.running_loss = figures['running_loss']
            site.running_loss_kwh = figures['running_loss_kwh']
            site.trigger_pct = figures['trigger_pct']
            site.status = status
            site.urgency_sequence = const.URGENCY_BY_STATUS[status]
            site.current_loss_pct = figures['current_loss_pct']
            site.avg_daily_loss = figures['avg_daily_loss']
            site.dust_rate_pct = figures['dust_rate_pct']
            site.days_to_trigger = days_to_trigger

    # ==================================================================
    # Value rules (DM-S-05): each message names the field and its range
    # ==================================================================
    @api.constrains('capacity_kwp')
    def _check_capacity_kwp(self):
        for site in self:
            if float_compare(site.capacity_kwp, 0.0,
                             precision_digits=const.KWH_DIGITS) <= 0:
                raise ValidationError(_("Capacity (kWp) must be greater than 0."))

    @api.constrains('price_per_kwh')
    def _check_price_per_kwh(self):
        for site in self:
            if float_compare(site.price_per_kwh, 0.0,
                             precision_digits=const.PRICE_DIGITS) <= 0:
                raise ValidationError(_(
                    "Electricity price (AED/kWh) must be greater than 0."))

    @api.constrains('cleaning_cost')
    def _check_cleaning_cost(self):
        for site in self:
            if float_compare(site.cleaning_cost, 0.0,
                             precision_digits=const.MONEY_DIGITS) <= 0:
                raise ValidationError(_("Cost of one clean must be greater than 0."))

    @api.constrains('performance_factor')
    def _check_performance_factor(self):
        for site in self:
            factor = site.performance_factor
            too_low = float_compare(
                factor, 0.0, precision_digits=const.FACTOR_DIGITS) <= 0
            too_high = float_compare(
                factor, const.MAX_PERFORMANCE_FACTOR,
                precision_digits=const.FACTOR_DIGITS) > 0
            if too_low or too_high:
                raise ValidationError(_(
                    "Performance factor must be greater than 0 and at most %(maximum)s.",
                    maximum='%g' % const.MAX_PERFORMANCE_FACTOR,
                ))

    # ==================================================================
    # Recommendation engine (specification section 5.6)
    # ==================================================================
    def _meets_recommendation_conditions(self):
        """REC-02: True only when all six conditions hold for this site."""
        self.ensure_one()
        jobs = self.job_ids
        # 1. The site is active.
        if not self.active:
            return False
        # 2. trigger_pct is 100 or more (the stored value, CAL-18).
        if float_compare(self.trigger_pct, const.TRIGGER_PCT,
                         precision_digits=const.PCT_DIGITS) < 0:
            return False
        # 3. The site has no job in state recommended or scheduled.
        if jobs.filtered(lambda job: job.state in const.OPEN_JOB_STATES):
            return False
        # 4. The site is not flagged for inspection.
        if self.fault_suspected:
            return False
        # 5. No done job of the site is still awaiting its result.
        if jobs.filtered(lambda job: job.state == 'done'
                         and job.recovery_state == 'pending'):
            return False
        # 6. The as-of date is at least 7 days after every dismissal.
        as_of = self._as_of_date()
        for job in jobs.filtered(lambda job: job.state == 'dismissed'
                                 and job.dismissed_date):
            if (as_of - job.dismissed_date).days < const.SNOOZE_DAYS:
                return False
        return True

    def _run_evaluation(self):
        """REC-01: recovery check, then recommendation check, per site.

        Runs after readings are created, once a day for all active sites, and
        on "Evaluate now". It runs with superuser rights (REC-07), so the
        result does not depend on who triggered it.

        The engine only ever creates jobs in state Recommended (C1). It never
        schedules, completes or dismisses a job, never assigns a crew and
        never changes last_cleaned_date (REC-05). Running it twice with no
        new data changes nothing (REC-06).
        """
        Job = self.env['dustwatch.cleaning.job'].sudo()
        for site in self.sudo():
            # Step 1 (WF-06): measure the result of finished cleans.
            site.job_ids.filtered(
                lambda job: job.state == 'done' and job.recovery_state == 'pending'
            )._check_recovery()

            # Step 2 (REC-03): an open DustWatch recommendation keeps live
            # figures until a manager accepts it (D4).
            open_job = site.job_ids.filtered(
                lambda job: job.state in const.OPEN_JOB_STATES)[:1]
            if open_job:
                if open_job.state == 'recommended' and open_job.origin == 'auto':
                    open_job._snapshot_reason()
                continue

            # Step 2 (REC-02, REC-04): create exactly one recommendation.
            if not site._meets_recommendation_conditions():
                continue
            job = Job.create({
                'site_id': site.id,
                'state': 'recommended',
                'origin': 'auto',
                'recommended_date': site._as_of_date(),
                'cost': site.cleaning_cost,
                'manager_id': site.manager_id.id,
            })
            job._snapshot_reason()
            job._notify_recommendation()
        return True

    @api.model
    def _cron_evaluate_sites(self):
        """Scheduled-action entry point: evaluate all active sites.

        Archived sites are skipped (FR-SITE-05).
        """
        self.sudo().search([('active', '=', True)])._run_evaluation()
        return True

    # ==================================================================
    # Chart data (FR-CHT-01 to FR-CHT-03)
    # ==================================================================
    def get_chart_data(self):
        """Data for the output chart of the site page.

        labels    ISO dates ascending, the last 120 readings
        expected  expected kWh per label, 1 decimal
        actual    actual kWh per label, 1 decimal
        cleans    ISO dates of the site's done jobs
        """
        self.ensure_one()
        readings = self.reading_ids.filtered('date').sorted('date')
        readings = readings[-const.CHART_MAX_POINTS:]
        done_jobs = self.job_ids.filtered(
            lambda job: job.state == 'done' and job.date_done)
        return {
            'labels': [fields.Date.to_string(reading.date) for reading in readings],
            'expected': [
                float_round(reading.expected_kwh, precision_digits=const.ONE_DECIMAL)
                for reading in readings
            ],
            'actual': [
                float_round(reading.actual_kwh, precision_digits=const.ONE_DECIMAL)
                for reading in readings
            ],
            'cleans': sorted(
                fields.Date.to_string(job.date_done) for job in done_jobs),
        }

    # ==================================================================
    # Buttons
    # ==================================================================
    def action_evaluate_now(self):
        """"Evaluate now" (FR-REC-08): run the evaluation on this site."""
        self._check_manager_rights()
        self._run_evaluation()
        return True

    def action_refresh_weather(self):
        """Refresh this site's forecast on a manager request."""
        self.ensure_one()
        self._check_manager_rights()
        stats = self.env['dustwatch.weather.forecast'].sudo()._refresh_sites(self)
        if stats.get('disabled'):
            message = _('Enable a weather provider in DustWatch / Configuration / Weather settings first.')
        else:
            message = _(
                'Weather refresh complete: %(rows)s daily forecast snapshots saved.',
                rows=stats.get('forecast_rows', 0),
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('DustWatch weather'),
                'message': message,
                'type': 'warning' if stats.get('failures') or stats.get('disabled') else 'success',
                'sticky': bool(stats.get('failures')),
            },
        }

    def action_open_simulator(self):
        """"Clean now vs wait" (FR-SIM-01): open the simulator dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Clean now vs wait"),
            'res_model': 'dustwatch.simulator',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_site_id': self.id},
        }

    def action_open_live_map(self):
        """Open this site's node on the live fleet map."""
        self.ensure_one()
        action = self.env.ref('dustwatch.action_dustwatch_live_map').read()[0]
        action['context'] = {
            'dustwatch_partner_id': self.partner_id.commercial_partner_id.id,
            'dustwatch_site_id': self.id,
        }
        return action

    def action_request_clean(self):
        """"Request clean" (WF-02, FR-REC-09): a manager books a clean.

        If the site already has an open job, that job opens and nothing is
        created. Otherwise a job is created directly in state Scheduled, for
        tomorrow, with origin "Requested by user" and a full snapshot.
        """
        self.ensure_one()
        self._check_manager_rights()
        job = self.open_job_id
        if not job:
            tomorrow = fields.Date.context_today(self) + timedelta(days=1)
            job = self.env['dustwatch.cleaning.job'].create({
                'site_id': self.id,
                'state': 'scheduled',
                'origin': 'manual',
                'recommended_date': self._as_of_date(),
                'scheduled_date': tomorrow,
                'cost': self.cleaning_cost,
                'manager_id': self.manager_id.id,
            })
            job._snapshot_reason()
            # The note reads "Clean requested by <user> for <site>." followed
            # by the figures (FR-EXP-06).
            job.message_post(body=job.explanation, subtype_xmlid=const.NOTE_SUBTYPE)
        return job._get_form_action()

    def action_mark_inspected(self):
        """"Mark inspected" (WF-07): clear the fault flag.

        The job that raised the flag keeps its result "No recovery".
        """
        self._check_manager_rights()
        for site in self.filtered('fault_suspected'):
            site.fault_suspected = False
            # Close the "Technical inspection" To-Do raised with the flag.
            inspection_todos = site.sudo().activity_ids.filtered(
                lambda activity: activity.summary == const.INSPECTION_SUMMARY)
            if inspection_todos:
                inspection_todos.action_feedback(feedback=_("Site inspected."))
            site.message_post(
                body=_(
                    "Inspection done: the \"Inspection needed\" flag was "
                    "cleared by %(user)s.",
                    user=self.env.user.name,
                ),
                subtype_xmlid=const.NOTE_SUBTYPE,
            )
        return True

    def action_view_readings(self):
        """Smart button "Readings": this site's readings (FR-SITE-04)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Readings"),
            'res_model': 'dustwatch.reading',
            'view_mode': 'list,graph,pivot,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }

    def action_view_jobs(self):
        """Smart button "Cleaning jobs": this site's jobs (FR-SITE-04)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Cleaning jobs"),
            'res_model': 'dustwatch.cleaning.job',
            'view_mode': 'list,kanban,form',
            'domain': [('site_id', '=', self.id)],
        }
