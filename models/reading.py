# -*- coding: utf-8 -*-
from odoo import models, fields, api

class DustwatchReading(models.Model):
    _name = 'dustwatch.reading'
    _description = 'Solar Daily Telemetry Reading'
    _order = 'date desc, site_id'
    _rec_name = 'display_name'

    site_id = fields.Many2one('dustwatch.site', string='Solar Site', required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True)
    sun_hours = fields.Float(string='Sunlight Hours', required=True, default=5.5,
                             help='Measured peak sun hours (PSH) for this day.')
    actual_kwh = fields.Float(string='Actual Output (kWh)', required=True,
                              help='Physical electricity recorded by on-site inverters.')
    expected_kwh = fields.Float(string='Expected Output (kWh)', compute='_compute_calculations', store=True,
                                help='Formula 6.1: Capacity x Sun Hours x Performance Factor.')
    lost_kwh = fields.Float(string='Lost Output (kWh)', compute='_compute_calculations', store=True,
                            help='Formula 6.2: max(0, Expected - Actual).')
    lost_aed = fields.Float(string='Money Lost (AED)', compute='_compute_calculations', store=True,
                            help='Formula 6.3: Lost kWh x Tariff.')
    soiling_loss_pct = fields.Float(string='Soiling Loss (%)', compute='_compute_calculations', store=True,
                                    help='Percentage deficit relative to theoretical clean capacity.')
    is_post_clean = fields.Boolean(string='Post-Clean Audit Day', default=False,
                                   help='Flagged during the 3-day recovery audit period following a clean.')
    notes = fields.Char(string='Notes / Weather Event')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('site_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.site_id.name or 'Site'} - {rec.date}"

    @api.depends('actual_kwh', 'sun_hours', 'site_id.capacity_kwp', 'site_id.performance_factor', 'site_id.electricity_price')
    def _compute_calculations(self):
        for rec in self:
            site = rec.site_id
            if site and rec.sun_hours > 0:
                # Formula 6.1: Expected = Capacity * Sun Hours * PR
                expected = site.capacity_kwp * rec.sun_hours * (site.performance_factor or 0.80)
                rec.expected_kwh = round(expected, 2)

                # Formula 6.2: Lost kWh = max(0, Expected - Actual)
                lost_units = max(0.0, rec.expected_kwh - rec.actual_kwh)
                rec.lost_kwh = round(lost_units, 2)

                # Formula 6.3: Money Lost = Lost kWh * Tariff
                rec.lost_aed = round(rec.lost_kwh * (site.electricity_price or 0.40), 2)

                # Percentage deficit
                if rec.expected_kwh > 0:
                    rec.soiling_loss_pct = round((rec.lost_kwh / rec.expected_kwh) * 100.0, 1)
                else:
                    rec.soiling_loss_pct = 0.0
            else:
                rec.expected_kwh = 0.0
                rec.lost_kwh = 0.0
                rec.lost_aed = 0.0
                rec.soiling_loss_pct = 0.0
