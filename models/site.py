# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DustwatchSite(models.Model):
    _name = 'dustwatch.site'
    _description = 'Solar Installation Site'
    _order = 'health_state desc, running_loss_aed desc, name'

    name = fields.Char(string='Site Name', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer / Owner', required=True, tracking=True)
    capacity_kwp = fields.Float(string='Capacity (kWp)', required=True, default=100.0,
                                help='System rated peak capacity in kilowatts (kWp).')
    electricity_price = fields.Float(string='Electricity Tariff (AED/kWh)', required=True, default=0.40,
                                     help='Value of electricity per unit (AED/kWh).')
    cleaning_cost = fields.Float(string='Cost of One Clean (AED)', required=True, default=1500.0,
                                 help='Contractor fee to clean all panels on this site.')
    performance_factor = fields.Float(string='Performance Factor (PR)', required=True, default=0.80,
                                      help='System baseline ratio (typically 0.75 - 0.85). Auto-tuned post-clean.')
    installation_date = fields.Date(string='Installation Date', default=fields.Date.context_today)
    date_last_cleaned = fields.Date(string='Date Last Cleaned', default=fields.Date.context_today,
                                    help='All readings since this date contribute to the running cumulative loss.')
    location = fields.Char(string='Location / City', default='Dubai, UAE')
    active = fields.Boolean(string='Active', default=True)

    # Relational Fields
    reading_ids = fields.One2many('dustwatch.reading', 'site_id', string='Daily Readings')
    job_ids = fields.One2many('dustwatch.job', 'site_id', string='Cleaning Jobs')

    # Computed Metrics
    reading_count = fields.Integer(string='Readings Count', compute='_compute_counts')
    job_count = fields.Integer(string='Jobs Count', compute='_compute_counts')
    running_loss_aed = fields.Float(string='Running Loss (AED)', compute='_compute_running_loss', store=True,
                                    help='Cumulative financial loss accumulated since the last clean date.')
    days_since_last_clean = fields.Integer(string='Days Since Last Clean', compute='_compute_running_loss', store=True)
    cleaning_progress = fields.Float(string='Soiling Progress (%)', compute='_compute_running_loss', store=True,
                                     help='Percentage of accumulated loss relative to cleaning cost threshold.')
    health_state = fields.Selection([
        ('green', 'Healthy (<70%)'),
        ('amber', 'Attention Needed (70%-99%)'),
        ('red', 'Clean Due (≥100%)'),
    ], string='Health Status', compute='_compute_running_loss', store=True, default='green')

    lifetime_saved_aed = fields.Float(string='Lifetime Savings (AED)', compute='_compute_lifetime_savings',
                                      help='Total financial return delivered through verified cleaning jobs.')

    @api.depends('reading_ids', 'job_ids')
    def _compute_counts(self):
        for site in self:
            site.reading_count = len(site.reading_ids)
            site.job_count = len(site.job_ids)

    @api.depends('reading_ids.lost_aed', 'date_last_cleaned', 'cleaning_cost')
    def _compute_running_loss(self):
        today = fields.Date.context_today(self)
        for site in self:
            # Calculate days since last clean
            if site.date_last_cleaned:
                delta = (today - site.date_last_cleaned).days
                site.days_since_last_clean = max(0, delta)
            else:
                site.days_since_last_clean = 0

            # Sum daily losses strictly after last clean date
            readings = site.reading_ids.filtered(
                lambda r: not site.date_last_cleaned or (r.date and r.date >= site.date_last_cleaned)
            )
            total_loss = sum(readings.mapped('lost_aed'))
            site.running_loss_aed = round(total_loss, 2)

            # Determine trigger threshold percentage
            if site.cleaning_cost > 0:
                progress = (site.running_loss_aed / site.cleaning_cost) * 100.0
                site.cleaning_progress = round(progress, 1)
            else:
                site.cleaning_progress = 0.0

            # Assign color status
            if site.cleaning_progress >= 100.0:
                site.health_state = 'red'
            elif site.cleaning_progress >= 70.0:
                site.health_state = 'amber'
            else:
                site.health_state = 'green'

    @api.depends('job_ids.state', 'job_ids.payback_days', 'job_ids.recovery_aed_day')
    def _compute_lifetime_savings(self):
        for site in self:
            completed_jobs = site.job_ids.filtered(lambda j: j.state == 'done')
            # Annualized recovery value created across completed jobs
            total_saved = sum(j.recovery_aed_day * 30.0 for j in completed_jobs)
            site.lifetime_saved_aed = round(total_saved, 2)

    def action_trigger_clean(self):
        """Manually trigger an automated cleaning job."""
        self.ensure_one()
        job = self.env['dustwatch.job'].create({
            'site_id': self.id,
            'trigger_loss_aed': self.running_loss_aed,
            'state': 'proposed',
            'cost': self.cleaning_cost,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cleaning Job'),
            'res_model': 'dustwatch.job',
            'res_id': job.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Daily Telemetry: %s') % self.name,
            'res_model': 'dustwatch.reading',
            'view_mode': 'graph,pivot,list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }

    def action_view_jobs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cleaning Jobs: %s') % self.name,
            'res_model': 'dustwatch.job',
            'view_mode': 'kanban,list,form',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id},
        }

    @api.model
    def cron_evaluate_cleaning_triggers(self):
        """Nightly cron to scan all sites and dispatch cleaning jobs for red-alert sites."""
        sites_due = self.search([
            ('active', '=', True),
            ('health_state', '=', 'red')
        ])
        for site in sites_due:
            # Check if there is already an open job (proposed or scheduled)
            open_jobs = site.job_ids.filtered(lambda j: j.state in ['proposed', 'scheduled'])
            if not open_jobs:
                self.env['dustwatch.job'].create({
                    'site_id': site.id,
                    'trigger_loss_aed': site.running_loss_aed,
                    'state': 'proposed',
                    'cost': site.cleaning_cost,
                })
