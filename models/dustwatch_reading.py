# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import constants as const
from .weather_utils import dubai_day_start_utc


class DustwatchReading(models.Model):
    """One day of output for one site (specification section 4.2).

    A manager types or imports four values: site, date, sun hours and actual
    output. Everything else on the reading is calculated (CAL-01 to CAL-04).
    """
    _name = 'dustwatch.reading'
    _description = 'Daily Reading'
    _order = 'date desc, id desc'   # DM-R-01

    # ------------------------------------------------------------------
    # Entered values
    # ------------------------------------------------------------------
    site_id = fields.Many2one(
        'dustwatch.site', string='Site',
        required=True, index=True, ondelete='cascade',   # deleted with its site
    )
    date = fields.Date(string='Date', required=True, index=True)
    sun_hours = fields.Float(
        string='Sun hours', digits=(16, const.KWH_DIGITS), required=True,
    )
    actual_kwh = fields.Float(
        string='Actual output (kWh)', digits=(16, const.KWH_DIGITS), required=True,
    )
    weather_forecast_id = fields.Many2one(
        'dustwatch.weather.forecast', string='Weather forecast used',
        readonly=True, copy=False, index=True, ondelete='set null',
    )

    # ------------------------------------------------------------------
    # Calculated values, stored and read-only (FR-READ-02)
    # ------------------------------------------------------------------
    expected_kwh = fields.Float(
        string='Expected output (kWh)', digits=(16, const.KWH_DIGITS),
        compute='_compute_loss', store=True,
    )
    lost_kwh = fields.Float(
        string='Lost to dust (kWh)', digits=(16, const.KWH_DIGITS),
        compute='_compute_loss', store=True,
    )
    loss_pct = fields.Float(
        string='Loss (%)', digits=(16, const.PCT_DIGITS),
        compute='_compute_loss', store=True,
        aggregator='avg',   # a percentage is averaged, never summed
    )
    lost_aed = fields.Monetary(
        string='Money lost', compute='_compute_loss', store=True,
    )
    forecast_sun_hours = fields.Float(
        string='Forecast peak-sun hours', related='weather_forecast_id.peak_sun_hours',
        store=True, readonly=True, digits=(16, const.KWH_DIGITS),
    )
    forecast_expected_kwh = fields.Float(
        string='Weather-based planned output (kWh)',
        related='weather_forecast_id.forecast_expected_kwh', store=True, readonly=True,
        digits=(16, const.KWH_DIGITS),
    )
    forecast_variance_kwh = fields.Float(
        string='Actual vs weather plan (kWh)', digits=(16, const.KWH_DIGITS),
        compute='_compute_weather_comparison', store=True,
    )
    forecast_error_pct = fields.Float(
        string='Weather forecast variance (%)', digits=(16, const.PCT_DIGITS),
        compute='_compute_weather_comparison', store=True, aggregator='avg',
    )

    # ------------------------------------------------------------------
    # Copies of site values, stored so they can be searched and grouped
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='site_id.currency_id', store=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='site_id.partner_id', store=True,
    )

    # DM-R-02: one reading per site per day, enforced by the database.
    _site_date_uniq = models.Constraint(
        'UNIQUE(site_id, date)',
        'A reading already exists for this site and date.',
    )

    # ------------------------------------------------------------------
    # Calculations
    # ------------------------------------------------------------------
    def _loss_values(self):
        """CAL-01 to CAL-04 for one reading, as unrounded numbers.

        This is the only place where the four reading formulas are written
        (ARC-05). The stored fields below save these numbers rounded; the
        site uses the unrounded loss % for its own formulas (CAL-18).
        """
        self.ensure_one()
        site = self.site_id
        # CAL-01: a cloudy day lowers the expected output in proportion to
        # its sun hours, so clouds never look like dust (FR-READ-04).
        expected_kwh = site.capacity_kwp * self.sun_hours * site.performance_factor
        # CAL-02: never below 0, even when the panels beat the expectation
        # (FR-READ-05).
        lost_kwh = max(expected_kwh - self.actual_kwh, 0.0)
        # CAL-03: guarded division (NFR-06).
        loss_pct = lost_kwh / expected_kwh * 100.0 if expected_kwh > 0 else 0.0
        # CAL-04
        lost_aed = lost_kwh * site.price_per_kwh
        return {
            'expected_kwh': expected_kwh,
            'lost_kwh': lost_kwh,
            'loss_pct': loss_pct,
            'lost_aed': lost_aed,
        }

    # DM-R-03: one method sets the four computed fields. Because it depends
    # on the site's settings, changing price, capacity or performance factor
    # recalculates every reading of that site (D8).
    @api.depends('sun_hours', 'actual_kwh', 'site_id.capacity_kwp',
                 'site_id.performance_factor', 'site_id.price_per_kwh')
    def _compute_loss(self):
        for reading in self:
            values = reading._loss_values()
            reading.expected_kwh = values['expected_kwh']
            reading.lost_kwh = values['lost_kwh']
            reading.loss_pct = values['loss_pct']
            reading.lost_aed = values['lost_aed']

    @api.depends('actual_kwh', 'forecast_expected_kwh')
    def _compute_weather_comparison(self):
        for reading in self:
            planned = reading.forecast_expected_kwh
            reading.forecast_variance_kwh = reading.actual_kwh - planned if reading.weather_forecast_id else 0.0
            reading.forecast_error_pct = (
                (reading.actual_kwh - planned) / planned * 100.0
                if reading.weather_forecast_id and planned > 0 else 0.0
            )

    def _attach_weather_forecasts(self):
        """Attach the latest forecast that existed before each Dubai day began.

        Keeping the issue time before the day prevents an in-day updated or
        post-event forecast from being mislabelled as a day-ahead prediction.
        """
        readings = self.filtered(lambda reading: reading.site_id and reading.date)
        if not readings:
            return True
        dates = set(readings.mapped('date'))
        cutoffs = {day: dubai_day_start_utc(day) for day in dates}
        forecasts = self.env['dustwatch.weather.forecast'].sudo().search([
            ('site_id', 'in', readings.mapped('site_id').ids),
            ('forecast_date', 'in', list(dates)),
            ('issued_at', '<=', max(cutoffs.values())),
        ], order='issued_at desc, id desc')
        latest_by_site_day = {}
        for forecast in forecasts:
            key = (forecast.site_id.id, forecast.forecast_date)
            if forecast.issued_at <= cutoffs[forecast.forecast_date] and key not in latest_by_site_day:
                latest_by_site_day[key] = forecast
        for reading in readings:
            forecast = latest_by_site_day.get((reading.site_id.id, reading.date))
            if forecast and reading.weather_forecast_id != forecast:
                reading.sudo().write({'weather_forecast_id': forecast.id})
        return True

    @api.constrains('site_id', 'date', 'weather_forecast_id')
    def _check_weather_forecast_matches_reading(self):
        for reading in self.filtered('weather_forecast_id'):
            forecast = reading.weather_forecast_id
            if forecast.site_id != reading.site_id or forecast.forecast_date != reading.date:
                raise ValidationError(_(
                    'The linked weather forecast must belong to the same site and date as the reading.'
                ))

    # DM-R-01: the display name is the site name and the date.
    @api.depends('site_id.name', 'date')
    def _compute_display_name(self):
        for reading in self:
            parts = [reading.site_id.name, fields.Date.to_string(reading.date)]
            reading.display_name = ' - '.join(part for part in parts if part)

    # ------------------------------------------------------------------
    # Value rules (DM-R-05): each message names the field and its range
    # ------------------------------------------------------------------
    @api.constrains('sun_hours')
    def _check_sun_hours(self):
        for reading in self:
            if reading.sun_hours < 0 or reading.sun_hours > const.MAX_SUN_HOURS:
                raise ValidationError(_(
                    "Sun hours must be between 0 and %(maximum)s.",
                    maximum='%g' % const.MAX_SUN_HOURS,
                ))

    @api.constrains('actual_kwh')
    def _check_actual_kwh(self):
        for reading in self:
            if reading.actual_kwh < 0:
                raise ValidationError(_("Actual output (kWh) must be 0 or more."))

    # ------------------------------------------------------------------
    # Create (DM-R-04, FR-READ-06)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Create the readings, then evaluate the affected sites once.

        An import creates many readings in one call. The evaluation runs a
        single time on the set of sites touched, not once per reading, so a
        recommendation can appear straight after an import.
        """
        readings = super().create(vals_list)
        readings._attach_weather_forecasts()
        readings.site_id._run_evaluation()
        return readings

    def write(self, vals):
        changed_location_or_date = bool({'site_id', 'date'} & vals.keys())
        result = super().write(vals)
        if changed_location_or_date:
            self.sudo().write({'weather_forecast_id': False})
            self._attach_weather_forecasts()
        return result
