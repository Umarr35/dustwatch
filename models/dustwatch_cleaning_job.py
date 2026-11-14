# -*- coding: utf-8 -*-
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from . import constants as const


class DustwatchCleaningJob(models.Model):
    """A clean of one site, from recommendation to measured result
    (specification sections 4.3 and 6.2).

    Lifecycle: Recommended -> Scheduled -> Done, or Dismissed.
    DustWatch can only create a job in Recommended. Every later move is a
    person pressing a button (C1, D5).
    """
    _name = 'dustwatch.cleaning.job'
    _description = 'Cleaning Job'
    _inherit = ['mail.thread', 'mail.activity.mixin']   # DM-J-01
    _order = 'id desc'

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    # Taken from the sequence with code dustwatch.cleaning.job: CLN/0001...
    name = fields.Char(string='Reference', readonly=True, copy=False, index=True)
    site_id = fields.Many2one(
        'dustwatch.site', string='Site',
        required=True, index=True, ondelete='cascade',   # deleted with its site
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='site_id.partner_id', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='site_id.currency_id', store=True,
    )
    manager_id = fields.Many2one('res.users', string='Operations manager')
    crew_user_id = fields.Many2one(
        'res.users', string='Assigned crew', ondelete='set null',
        domain=[('share', '=', False)],   # internal users only
    )
    # WF-09: read-only in every view. Only the action_* methods below and
    # the engine write it.
    state = fields.Selection(
        const.JOB_STATES, string='Status', default='recommended',
        required=True, readonly=True, copy=False, index=True,
        group_expand='_group_expand_states',
    )
    origin = fields.Selection(
        const.JOB_ORIGINS, string='Origin', default='auto',
        required=True, readonly=True,
    )
    # The site's as-of date when the job was created.
    recommended_date = fields.Date(string='Recommended on', readonly=True)
    scheduled_date = fields.Date(string='Scheduled for')   # set by WF-02 or WF-03
    date_done = fields.Date(string='Cleaned on', copy=False)   # set by WF-05
    # The site's as-of date at dismissal.
    dismissed_date = fields.Date(string='Dismissed on', readonly=True, copy=False)
    dismiss_reason = fields.Char(string='Reason for dismissal', copy=False)
    cost = fields.Monetary(string='Cost of clean')

    # ------------------------------------------------------------------
    # Reason snapshot (E2), all read-only: the numbers behind the job
    # ------------------------------------------------------------------
    snapshot_date = fields.Date(string='Figures as of', readonly=True)
    trigger_running_loss = fields.Monetary(string='Lost since last clean', readonly=True)
    trigger_cleaning_cost = fields.Monetary(string='Cost of one clean', readonly=True)
    trigger_pct = fields.Float(
        string='% of trigger', digits=(16, const.PCT_DIGITS), readonly=True,
        aggregator='avg',
    )
    trigger_days_since_clean = fields.Integer(
        string='Days since clean', readonly=True, aggregator='avg',
    )
    trigger_last_cleaned_date = fields.Date(string='Last cleaned', readonly=True)
    trigger_loss_pct = fields.Float(
        string='Current loss (%)', digits=(16, const.PCT_DIGITS), readonly=True,
        aggregator='avg',
    )
    trigger_avg_daily_loss = fields.Monetary(string='Losing per day', readonly=True)
    trigger_dust_rate_pct = fields.Float(
        string='Dust rate (% per day)', digits=(16, const.DUST_RATE_DIGITS),
        readonly=True, aggregator='avg',
    )
    trigger_wait_cost = fields.Monetary(
        string='Extra loss if waiting 7 days', readonly=True,
    )
    explanation = fields.Html(string='Why this recommendation', readonly=True)

    # ------------------------------------------------------------------
    # Result of the clean, all read-only. Empty until the job is done.
    # ------------------------------------------------------------------
    recovery_state = fields.Selection(
        const.RECOVERY_STATES, string='Result', readonly=True, copy=False,
    )
    loss_before_per_day = fields.Monetary(
        string='Loss before (AED/day)', readonly=True, copy=False,
    )
    loss_after_per_day = fields.Monetary(
        string='Loss after (AED/day)', readonly=True, copy=False,
    )
    loss_pct_before = fields.Float(
        string='Loss before (%)', digits=(16, const.PCT_DIGITS),
        readonly=True, copy=False, aggregator='avg',
    )
    loss_pct_after = fields.Float(
        string='Loss after (%)', digits=(16, const.PCT_DIGITS),
        readonly=True, copy=False, aggregator='avg',
    )
    recovery_per_day = fields.Monetary(
        string='Recovered per day', readonly=True, copy=False,
    )
    recovery_pct = fields.Float(
        string='Recovery (%)', digits=(16, const.ONE_DECIMAL),
        readonly=True, copy=False, aggregator='avg',
    )
    payback_days = fields.Float(
        string='Payback (days)', digits=(16, const.ONE_DECIMAL),
        readonly=True, copy=False,
        aggregator='avg',   # FR-RPT-03: payback days are averaged
    )

    # ==================================================================
    # Create and constraints
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """DM-J-02: number each job and fill the site-based defaults."""
        Site = self.env['dustwatch.site']
        Sequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = (
                    Sequence.next_by_code('dustwatch.cleaning.job') or _("New"))
            site = Site.browse(vals.get('site_id'))
            if site:
                # Defaults taken from the site: its manager and its cost.
                if 'manager_id' not in vals:
                    vals['manager_id'] = site.manager_id.id
                if 'cost' not in vals:
                    vals['cost'] = site.cleaning_cost
            # A job created directly in state done, as in the sample data,
            # still has to be measured.
            if vals.get('state') == 'done' and not vals.get('recovery_state'):
                vals['recovery_state'] = 'pending'
        return super().create(vals_list)

    # DM-J-03 / FR-REC-06: a site never has two open jobs.
    @api.constrains('site_id', 'state')
    def _check_single_open_job(self):
        for job in self:
            if job.state not in const.OPEN_JOB_STATES:
                continue
            open_jobs = self.search_count([
                ('site_id', '=', job.site_id.id),
                ('state', 'in', const.OPEN_JOB_STATES),
            ])
            if open_jobs > 1:
                raise ValidationError(_("This site already has an open cleaning job."))

    # DM-J-04: grouping by status always shows Recommended, Scheduled and
    # Done, in that order, even when empty. Dismissed appears only when the
    # search actually returns dismissed jobs. ("order" is passed by older
    # Odoo versions only.)
    @api.model
    def _group_expand_states(self, states, domain, order=None):
        return [
            key for key, _label in const.JOB_STATES
            if key in const.BOARD_JOB_STATES or key in states
        ]

    # ==================================================================
    # Explainable recommendations (E2, specification section 7.5)
    # ==================================================================
    def _snapshot_reason(self):
        """DM-J-05: store the numbers behind the job and their explanation.

        Called when a job is created (WF-01, WF-02) and again by every
        evaluation while the job is still Recommended (REC-03). After
        "Accept" nothing calls it any more, so the figures freeze (D4).
        """
        for job in self:
            site = job.site_id
            snapshot = {
                'snapshot_date': site._as_of_date(),
                'trigger_running_loss': site.running_loss,
                'trigger_cleaning_cost': site.cleaning_cost,
                'trigger_pct': site.trigger_pct,
                'trigger_days_since_clean': site.days_since_clean,
                'trigger_last_cleaned_date': site.last_cleaned_date,
                'trigger_loss_pct': site.current_loss_pct,
                'trigger_avg_daily_loss': site.avg_daily_loss,
                'trigger_dust_rate_pct': site.dust_rate_pct,
                'trigger_wait_cost': site._projected_loss(const.DEFAULT_WAIT_DAYS),
            }
            snapshot['explanation'] = job._build_explanation(snapshot)
            job.write(snapshot)

    def _build_explanation(self, snapshot):
        """FR-EXP-02: the plain-language reason, as HTML.

        The first line is a bold paragraph, the four points are a bullet
        list and the rule line is a paragraph. Amounts are whole AED with
        thousands separators; percentages have 1 decimal, except % of
        trigger, which has none; dates read like 30 Sep 2026.
        """
        self.ensure_one()
        Site = self.env['dustwatch.site']
        number = Site._format_number

        if self.origin == 'manual':
            # FR-EXP-06: a manually requested job names the user.
            headline = _(
                "Clean requested by %(user)s for %(site)s.",
                user=self.env.user.name, site=self.site_id.name,
            )
        else:
            headline = _("Cleaning recommended for %(site)s.", site=self.site_id.name)

        bullets = [
            _(
                "Lost since the last clean: AED %(loss)s over %(days)s days "
                "(last cleaned %(date)s).",
                loss=number(snapshot['trigger_running_loss']),
                days=snapshot['trigger_days_since_clean'],
                date=Site._format_date(snapshot['trigger_last_cleaned_date']),
            ),
            _(
                "Cost of one clean: AED %(cost)s. The loss has reached "
                "%(pct)s%% of that cost.",
                cost=number(snapshot['trigger_cleaning_cost']),
                pct=number(snapshot['trigger_pct']),
            ),
            _(
                "Current performance: %(pct)s%% below expected output, about "
                "AED %(daily)s lost per day.",
                pct=number(snapshot['trigger_loss_pct'], const.ONE_DECIMAL),
                daily=number(snapshot['trigger_avg_daily_loss']),
            ),
            _(
                "Waiting %(days)s more days would lose about AED %(loss)s more.",
                days=const.DEFAULT_WAIT_DAYS,
                loss=number(snapshot['trigger_wait_cost']),
            ),
        ]

        # Markup escapes the inserted texts (a site name may contain "&").
        html = Markup("<p><strong>%s</strong></p>") % headline
        html += Markup("<ul>%s</ul>") % Markup("").join(
            Markup("<li>%s</li>") % bullet for bullet in bullets)
        if self.origin != 'manual':
            # The rule line is left out for a manually requested job.
            html += Markup("<p>%s</p>") % _(
                "Rule applied: recommend a clean when the money lost since "
                "the last clean reaches the cost of one clean.")
        return html

    def _notify_recommendation(self):
        """FR-REC-03 and FR-EXP-04: tell the manager about a new recommendation.

        The explanation is posted as an internal note and used as the note of
        a To-Do "Review cleaning recommendation", due today. No email is
        sent (FR-NTF-01): the context key below stops the activity from
        mailing the assigned user.
        """
        for job in self:
            job.message_post(body=job.explanation, subtype_xmlid=const.NOTE_SUBTYPE)
            manager = job.site_id.manager_id or job.manager_id
            job.with_context(mail_activity_quick_update=True).activity_schedule(
                const.TODO_ACTIVITY_TYPE,
                date_deadline=fields.Date.context_today(job),
                summary=const.REVIEW_SUMMARY,
                note=job.explanation,
                user_id=manager.id or self.env.uid,
            )

    # ==================================================================
    # Recovery, payback and fault (specification section 5.4)
    # ==================================================================
    def _check_recovery(self):
        """WF-06: measure what a finished clean recovered (CAL-15, CAL-16).

        Runs once per job, when three readings exist after its clean date.
        A stored result never changes afterwards (FR-RCV-05), because only
        jobs still "Awaiting readings" are processed. The site-side effects
        need superuser rights (WF-10).
        """
        Site = self.env['dustwatch.site']
        for job in self.sudo():
            if job.state != 'done' or job.recovery_state != 'pending' or not job.date_done:
                continue
            site = job.site_id
            clean_date = job.date_done
            readings = site.reading_ids.filtered('date').sorted('date')
            # A reading dated on the clean date belongs to neither window.
            after = readings.filtered(lambda reading: reading.date > clean_date)
            after = after[:const.RECOVERY_WINDOW]
            if len(after) < const.RECOVERY_WINDOW:
                continue   # still awaiting readings (FR-RCV-01)
            before = readings.filtered(lambda reading: reading.date < clean_date)
            before = before[-const.RECOVERY_WINDOW:]

            # CAL-15, on unrounded values (CAL-18). Every division is guarded.
            loss_before = Site._mean(before.mapped('lost_aed'))
            loss_after = Site._mean(after.mapped('lost_aed'))
            pct_before = Site._mean(r._loss_values()['loss_pct'] for r in before)
            pct_after = Site._mean(r._loss_values()['loss_pct'] for r in after)
            recovery = max(loss_before - loss_after, 0.0)
            recovery_pct = 0.0
            if not float_is_zero(loss_before, precision_digits=const.MONEY_DIGITS):
                recovery_pct = recovery / loss_before * 100.0
            payback_days = 0.0
            if not float_is_zero(recovery, precision_digits=const.MONEY_DIGITS):
                payback_days = job.cost / recovery

            job.write({
                'loss_before_per_day': loss_before,
                'loss_after_per_day': loss_after,
                'loss_pct_before': pct_before,
                'loss_pct_after': pct_after,
                'recovery_per_day': recovery,
                'recovery_pct': recovery_pct,
                'payback_days': payback_days,
            })

            # CAL-16, decided on the stored values (CAL-18): a clean that
            # brings back less than half of a real loss points to a fault.
            is_fault = (
                float_compare(job.loss_pct_before, const.FAULT_MIN_LOSS_PCT,
                              precision_digits=const.PCT_DIGITS) >= 0
                and float_compare(job.recovery_pct, const.FAULT_MAX_RECOVERY_PCT,
                                  precision_digits=const.ONE_DECIMAL) < 0
            )
            job.recovery_state = 'fault' if is_fault else 'confirmed'

            # FR-RCV-04: a note on the job states the result.
            job.message_post(body=job._result_sentence(), subtype_xmlid=const.NOTE_SUBTYPE)

            if is_fault:
                # FR-FAU-01 and FR-FAU-03: flag the site and ask the manager
                # for a technical inspection.
                site.fault_suspected = True
                manager = site.manager_id
                site.with_context(mail_activity_quick_update=True).activity_schedule(
                    const.TODO_ACTIVITY_TYPE,
                    date_deadline=fields.Date.context_today(site),
                    summary=const.INSPECTION_SUMMARY,
                    note=_(
                        "Output did not recover after the last clean. "
                        "A technical inspection is recommended."),
                    user_id=manager.id or self.env.uid,
                )

    def _result_sentence(self):
        """FR-RCV-04: the sentence that states the result of the clean."""
        self.ensure_one()
        number = self.env['dustwatch.site']._format_number
        before = number(self.loss_before_per_day, const.MONEY_DIGITS)
        after = number(self.loss_after_per_day, const.MONEY_DIGITS)
        if self.recovery_state == 'confirmed':
            return _(
                "Clean confirmed: loss fell from AED %(before)s/day to AED "
                "%(after)s/day. The AED %(cost)s clean pays for itself in "
                "%(payback)s days.",
                before=before, after=after, cost=number(self.cost),
                payback=number(self.payback_days, const.ONE_DECIMAL),
            )
        if self.recovery_state == 'fault':
            return _(
                "No recovery after this clean: loss was AED %(before)s/day "
                "before and AED %(after)s/day after. Dust is unlikely to be "
                "the cause.",
                before=before, after=after,
            )
        return ''

    # ==================================================================
    # Lifecycle buttons (specification section 6.2)
    # Any transition not written here is rejected (WF-08).
    # ==================================================================
    def action_accept(self):
        """WF-03 "Accept": Recommended -> Scheduled (managers)."""
        self.env['dustwatch.site']._check_manager_rights()
        for job in self:
            if job.state != 'recommended':
                raise UserError(_("Only a recommended job can be accepted."))
            values = {'state': 'scheduled'}
            if not job.scheduled_date:
                # "Tomorrow" is the day after today's date (WF-11).
                values['scheduled_date'] = (
                    fields.Date.context_today(job) + timedelta(days=1))
            job.write(values)

            # The review To-Do is marked done.
            review_todos = job.sudo().activity_ids.filtered(
                lambda activity: activity.summary == const.REVIEW_SUMMARY)
            if review_todos:
                review_todos.action_feedback(feedback=_("Recommendation accepted."))

            # An assigned crew member gets a To-Do "Clean <site>", due on the
            # scheduled date.
            if job.crew_user_id:
                job.with_context(mail_activity_quick_update=True).activity_schedule(
                    const.TODO_ACTIVITY_TYPE,
                    date_deadline=job.scheduled_date,
                    summary=_("Clean %(site)s", site=job.site_id.name),
                    user_id=job.crew_user_id.id,
                )
        return True

    def action_dismiss(self):
        """WF-04 "Dismiss": Recommended or Scheduled -> Dismissed (managers).

        The site then gets no new automatic recommendation until its as-of
        date is 7 days past the dismissal (REC-02, condition 6).
        """
        self.env['dustwatch.site']._check_manager_rights()
        for job in self:
            if job.state not in const.OPEN_JOB_STATES:
                raise UserError(_(
                    "Only a recommended or scheduled job can be dismissed."))
            if not (job.dismiss_reason or '').strip():
                raise UserError(_("Enter a reason before dismissing."))
            job.write({
                'state': 'dismissed',
                'dismissed_date': job.site_id._as_of_date(),
            })
            # Open activities on the job are cancelled.
            job.sudo().activity_ids.unlink()
            job.message_post(
                body=_("Dismissed. Reason: %(reason)s", reason=job.dismiss_reason),
                subtype_xmlid=const.NOTE_SUBTYPE,
            )
        return True

    def action_done(self):
        """WF-05 "Mark done": Scheduled -> Done (crew or managers).

        Marking a job done resets the site's running loss, because the
        site's last-cleaned date moves to the clean date. The site is
        written with superuser rights, so a crew member without write access
        to sites can still confirm a clean (WF-10).
        """
        for job in self:
            if job.state != 'scheduled':
                raise UserError(_("Only a scheduled job can be marked done."))
            date_done = job.date_done or fields.Date.context_today(job)
            site = job.site_id.sudo()
            if date_done <= site.last_cleaned_date:
                raise UserError(_(
                    "The clean date must be after the site's last clean."))

            job.write({
                'state': 'done',
                'date_done': date_done,
                'recovery_state': 'pending',
            })
            site.last_cleaned_date = date_done

            # Open activities on the job are marked done.
            open_activities = job.sudo().activity_ids
            if open_activities:
                open_activities.action_feedback(feedback=_("Clean done."))

            site.message_post(
                body=_(
                    "Cleaned on %(date)s (%(job)s).",
                    date=site._format_date(date_done), job=job.name,
                ),
                subtype_xmlid=const.NOTE_SUBTYPE,
            )
            # The recovery check then runs at once.
            job._check_recovery()
        return True

    # ==================================================================
    # Other buttons
    # ==================================================================
    def action_open_simulator(self):
        """"Clean now vs wait" (FR-SIM-01): open the simulator for the site."""
        self.ensure_one()
        return self.site_id.action_open_simulator()

    def action_send_to_owner(self):
        """"Send to owner" (FR-NTF-02): open the email composer.

        The email is addressed to the site's customer. Its body is the
        explanation for an open job, or the result sentence for a done job.
        Nothing is sent until the manager reviews it and presses Send.
        """
        self.ensure_one()
        self.env['dustwatch.site']._check_manager_rights()
        if self.state == 'done':
            sentence = self._result_sentence() or _(
                "Cleaned on %(date)s. The result will be measured after "
                "three more days of readings.",
                date=self.env['dustwatch.site']._format_date(self.date_done),
            )
            body = Markup("<p>%s</p>") % sentence
        else:
            body = self.explanation or Markup("")
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send to owner"),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_ids': self.ids,
                'default_composition_mode': 'comment',
                'default_partner_ids': self.partner_id.ids,
                'default_subject': _(
                    "%(site)s: cleaning job %(job)s",
                    site=self.site_id.name, job=self.name),
                'default_body': body,
            },
        }

    def _get_form_action(self):
        """An action that opens this job's page."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Cleaning job"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
