# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models import constants as const


class DustwatchSimulator(models.TransientModel):
    """Clean Now vs Wait dialog (specification sections 4.4 and 5.3, E1).

    A transient model: nothing it holds is kept after the dialog closes, and
    it writes nothing to sites, readings or jobs (DM-W-01, FR-SIM-05).

    It compares the cost per day of the current cleaning cycle under two
    plans. Both plans pay for one clean, so comparing only the next 7 days
    would make "clean now" win every time (D6). Spreading each plan's total
    cost over the length of its cycle shows what waiting buys: fewer cleans
    per year.
    """
    _name = 'dustwatch.simulator'
    _description = 'Clean Now vs Wait'

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    site_id = fields.Many2one(
        'dustwatch.site', string='Site', required=True, ondelete='cascade',
    )
    wait_days = fields.Integer(string='Days to wait', default=const.DEFAULT_WAIT_DAYS)

    # ------------------------------------------------------------------
    # Read-only context figures, straight from the site
    # ------------------------------------------------------------------
    currency_id = fields.Many2one(related='site_id.currency_id', string='Currency')
    days_since_clean = fields.Integer(related='site_id.days_since_clean')
    running_loss = fields.Monetary(related='site_id.running_loss')
    cleaning_cost = fields.Monetary(related='site_id.cleaning_cost')
    current_loss_pct = fields.Float(related='site_id.current_loss_pct')
    avg_daily_loss = fields.Monetary(related='site_id.avg_daily_loss')
    dust_rate_pct = fields.Float(related='site_id.dust_rate_pct')
    days_to_trigger = fields.Integer(related='site_id.days_to_trigger')
    # Helper for the dialog only: decides which footer button is shown
    # ("Request clean" or "Open cleaning job", FR-SIM-06).
    open_job_id = fields.Many2one(related='site_id.open_job_id', string='Open job')

    # ------------------------------------------------------------------
    # Results (CAL-14), all set by _compute_simulation.
    # The two columns of the dialog share the same labels on screen
    # ("Cycle length (days)", "Electricity lost"...). The Python labels carry
    # a "Clean now:" or "Wait:" prefix so that they stay unique and Odoo does
    # not log a "same label" warning (NFR-01).
    # ------------------------------------------------------------------
    uses_default_rate = fields.Boolean(
        string='Default dust rate used', compute='_compute_simulation',
    )
    extra_loss_if_wait = fields.Monetary(
        string='Extra electricity lost by waiting', compute='_compute_simulation',
    )
    now_cycle_days = fields.Integer(
        string='Clean now: cycle length (days)', compute='_compute_simulation',
    )
    wait_cycle_days = fields.Integer(
        string='Wait: cycle length (days)', compute='_compute_simulation',
    )
    now_electricity_loss = fields.Monetary(
        string='Clean now: electricity lost', compute='_compute_simulation',
    )
    wait_electricity_loss = fields.Monetary(
        string='Wait: electricity lost', compute='_compute_simulation',
    )
    now_cleaning_cost = fields.Monetary(
        string='Clean now: cleaning cost', compute='_compute_simulation',
    )
    wait_cleaning_cost = fields.Monetary(
        string='Wait: cleaning cost', compute='_compute_simulation',
    )
    now_total = fields.Monetary(
        string='Clean now: total cost of the cycle', compute='_compute_simulation',
    )
    wait_total = fields.Monetary(
        string='Wait: total cost of the cycle', compute='_compute_simulation',
    )
    now_cost_per_day = fields.Monetary(
        string='Clean now: cost per day', compute='_compute_simulation',
    )
    wait_cost_per_day = fields.Monetary(
        string='Wait: cost per day', compute='_compute_simulation',
    )
    verdict = fields.Selection(
        const.SIMULATOR_VERDICTS, string='Verdict', compute='_compute_simulation',
    )
    saving_per_day = fields.Monetary(
        string='Saving per day', compute='_compute_simulation',
    )
    saving_per_year = fields.Monetary(
        string='Saving per year', compute='_compute_simulation',
    )
    verdict_text = fields.Char(string='Verdict text', compute='_compute_simulation')

    # ==================================================================
    # CAL-14: every result comes from this one method
    # ==================================================================
    @api.depends('site_id', 'wait_days')
    def _compute_simulation(self):
        number = self.env['dustwatch.site']._format_number
        for simulator in self:
            site = simulator.site_id
            if not site:
                simulator.update({
                    'uses_default_rate': False, 'extra_loss_if_wait': 0.0,
                    'now_cycle_days': 0, 'wait_cycle_days': 0,
                    'now_electricity_loss': 0.0, 'wait_electricity_loss': 0.0,
                    'now_cleaning_cost': 0.0, 'wait_cleaning_cost': 0.0,
                    'now_total': 0.0, 'wait_total': 0.0,
                    'now_cost_per_day': 0.0, 'wait_cost_per_day': 0.0,
                    'verdict': False, 'saving_per_day': 0.0,
                    'saving_per_year': 0.0, 'verdict_text': False,
                })
                continue

            # n is kept inside its allowed range while the user is typing;
            # saving an out-of-range value is refused by the constraint.
            wait_days = min(max(simulator.wait_days, const.MIN_WAIT_DAYS),
                            const.MAX_WAIT_DAYS)
            running_loss = site.running_loss                  # R
            cleaning_cost = site.cleaning_cost                # C
            cycle_days = max(site.days_since_clean, 1)        # d, at least 1
            extra_loss = site._projected_loss(wait_days)      # W

            now_total = running_loss + cleaning_cost                  # R + C
            wait_total = running_loss + extra_loss + cleaning_cost    # R + W + C
            now_per_day = now_total / cycle_days
            wait_per_day = wait_total / (cycle_days + wait_days)

            # The plan with the lower cost per day wins; a tie means clean now.
            clean_now = now_per_day <= wait_per_day
            # Unrounded on purpose: the yearly saving is the unrounded daily
            # saving x 365 (CAL-14).
            saving_per_day = abs(now_per_day - wait_per_day)
            saving_per_year = saving_per_day * 365

            # FR-SIM-04: costs per day have 2 decimals, other amounts are
            # whole AED.
            texts = {
                'days': wait_days,
                'extra': number(extra_loss),
                'now': number(now_per_day, const.MONEY_DIGITS),
                'wait': number(wait_per_day, const.MONEY_DIGITS),
                'year': number(saving_per_year),
            }
            if clean_now:
                verdict_text = _(
                    "Clean now. Waiting %(days)s days would lose about AED "
                    "%(extra)s more electricity and raise this cycle's cost "
                    "from AED %(now)s/day to AED %(wait)s/day, about AED "
                    "%(year)s a year.", **texts)
            else:
                verdict_text = _(
                    "Wait. Cleaning in %(days)s days brings this cycle's cost "
                    "down from AED %(now)s/day to AED %(wait)s/day, about AED "
                    "%(year)s a year, even after losing about AED %(extra)s "
                    "more electricity.", **texts)

            # FR-SIM-08: True when CAL-10 fell back to the default dust rate.
            simulator.uses_default_rate = (
                site.days_since_clean < const.MIN_DAYS_FOR_DUST_RATE)
            simulator.extra_loss_if_wait = extra_loss
            simulator.now_cycle_days = cycle_days
            simulator.wait_cycle_days = cycle_days + wait_days
            simulator.now_electricity_loss = running_loss
            simulator.wait_electricity_loss = running_loss + extra_loss
            simulator.now_cleaning_cost = cleaning_cost
            simulator.wait_cleaning_cost = cleaning_cost
            simulator.now_total = now_total
            simulator.wait_total = wait_total
            simulator.now_cost_per_day = now_per_day
            simulator.wait_cost_per_day = wait_per_day
            simulator.verdict = 'clean_now' if clean_now else 'wait'
            simulator.saving_per_day = saving_per_day
            simulator.saving_per_year = saving_per_year
            simulator.verdict_text = verdict_text

    # "Days to wait" is editable from 1 to 60 (FR-SIM-09).
    @api.constrains('wait_days')
    def _check_wait_days(self):
        for simulator in self:
            if not const.MIN_WAIT_DAYS <= simulator.wait_days <= const.MAX_WAIT_DAYS:
                raise ValidationError(_(
                    "Days to wait must be between %(minimum)s and %(maximum)s.",
                    minimum=const.MIN_WAIT_DAYS, maximum=const.MAX_WAIT_DAYS,
                ))

    # ==================================================================
    # Footer buttons (FR-SIM-06)
    # ==================================================================
    def action_request_clean(self):
        """"Request clean": hand over to the site (WF-02)."""
        self.ensure_one()
        return self.site_id.action_request_clean()

    def action_open_job(self):
        """"Open cleaning job": open the site's open job."""
        self.ensure_one()
        job = self.site_id.open_job_id
        if not job:
            return {'type': 'ir.actions.act_window_close'}
        return job._get_form_action()
