# -*- coding: utf-8 -*-
"""Automated tests TS-01 to TS-14 (specification section 11, NFR-08).

Run them with:

    odoo-bin -d <database> -i dustwatch --test-enable --test-tags /dustwatch --stop-after-init

Every scenario uses the reference site T1 of section 5: 500 kWp, AED 0.40 per
kWh, AED 1,500 per clean, performance factor 0.80, last cleaned 2026-09-30.
Its reading for day i is dated 2026-09-30 plus i days, with 5.5 sun hours and
actual output 2,200 x (1 - 0.002 x i).

Each test starts from a T1 with no readings and no jobs: Odoo rolls the
database back after every test method.
"""
import html
import re
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import constants as const

T1_LAST_CLEANED = date(2026, 9, 30)

# The T1 explanation of section 7.5, sentence by sentence.
T1_EXPLANATION = [
    "Cleaning recommended for T1.",
    "Lost since the last clean: AED 1,515 over 41 days (last cleaned 30 Sep 2026).",
    "Cost of one clean: AED 1,500. The loss has reached 101% of that cost.",
    "Current performance: 8.0% below expected output, about AED 70 lost per day.",
    "Waiting 7 more days would lose about AED 554 more.",
    "Rule applied: recommend a clean when the money lost since the last clean "
    "reaches the cost of one clean.",
]


@tagged('post_install', '-at_install')
class TestDustwatch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Site = cls.env['dustwatch.site']
        cls.Reading = cls.env['dustwatch.reading']
        cls.Job = cls.env['dustwatch.cleaning.job']
        cls.Simulator = cls.env['dustwatch.simulator']
        cls.customer = cls.env['res.partner'].create({'name': 'T1 Customer'})
        cls.manager = cls.env.ref('base.user_admin')

        # A crew member, for the To-Do created when a job is accepted.
        cls.crew_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DustWatch Crew Test',
            'login': 'dustwatch_crew_test',
            'email': 'dustwatch.crew@example.com',
        })
        crew_group = cls.env.ref('dustwatch.group_dustwatch_crew')
        # The field is user_ids on Odoo 19 (users on older versions).
        users_field = 'user_ids' if 'user_ids' in crew_group._fields else 'users'
        crew_group.write({users_field: [(4, cls.crew_user.id)]})

        cls.t1 = cls._new_site('T1')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _new_site(cls, name, capacity=500.0, cleaning_cost=1500.0):
        return cls.Site.create({
            'name': name,
            'partner_id': cls.customer.id,
            'manager_id': cls.manager.id,
            'capacity_kwp': capacity,
            'price_per_kwh': 0.40,
            'cleaning_cost': cleaning_cost,
            'performance_factor': 0.80,
            'last_cleaned_date': T1_LAST_CLEANED,
        })

    def _load_day(self, site, day, extra_loss=0.0):
        """Create the reading of day `day`: dust takes 0.2 points a day."""
        expected = site.capacity_kwp * 5.5 * site.performance_factor
        return self.Reading.create({
            'site_id': site.id,
            'date': T1_LAST_CLEANED + timedelta(days=day),
            'sun_hours': 5.5,
            'actual_kwh': expected * (1 - 0.002 * day - extra_loss),
        })

    def _load_days(self, site, first, last, extra_loss=0.0):
        """Load days first..last, one day at a time."""
        for day in range(first, last + 1):
            self._load_day(site, day, extra_loss)

    def _jobs(self, site):
        """The site's jobs, oldest first."""
        return self.Job.search([('site_id', '=', site.id)], order='id')

    def _activities(self, record, summary=None):
        """The open activities of a record, optionally with one summary."""
        domain = [('res_model', '=', record._name), ('res_id', '=', record.id)]
        if summary:
            domain.append(('summary', '=', summary))
        return self.env['mail.activity'].search(domain)

    def _messages(self, record, text):
        """The chatter messages of a record that contain `text`."""
        messages = self.env['mail.message'].search([
            ('model', '=', record._name), ('res_id', '=', record.id)])
        return messages.filtered(lambda message: text in self._plain(message.body))

    @staticmethod
    def _plain(html_text):
        """HTML to plain text on one line, for comparing sentences."""
        text = re.sub(r'<[^>]+>', ' ', html_text or '')
        return re.sub(r'\s+', ' ', html.unescape(text)).strip()

    def _simulate(self, site, wait_days=const.DEFAULT_WAIT_DAYS):
        return self.Simulator.create({'site_id': site.id, 'wait_days': wait_days})

    def _recommend_and_clean_t1(self):
        """TS-09 steps: days 1-41, accept with a crew member, clean on 11 Nov."""
        self._load_days(self.t1, 1, 41)
        job = self._jobs(self.t1)
        job.crew_user_id = self.crew_user
        job.action_accept()
        job.date_done = date(2026, 11, 11)
        job.action_done()
        return job

    def assertMoney(self, value, expected, msg=None):
        """Money must match to within AED 0.01 (CAL-18)."""
        self.assertAlmostEqual(value, expected, delta=0.0051, msg=msg)

    # ------------------------------------------------------------------
    # 11.1 Calculations
    # ------------------------------------------------------------------
    def test_ts01_reading_formulas(self):
        """TS-01: CAL-01 to CAL-04 on one reading."""
        reading = self.Reading.create({
            'site_id': self.t1.id, 'date': date(2026, 10, 1),
            'sun_hours': 5.5, 'actual_kwh': 2112.00,
        })
        self.assertAlmostEqual(reading.expected_kwh, 2200.00, places=2)
        self.assertAlmostEqual(reading.lost_kwh, 88.00, places=2)
        self.assertAlmostEqual(reading.loss_pct, 4.00, places=2)
        self.assertMoney(reading.lost_aed, 35.20)

    def test_ts02_cloudy_day(self):
        """TS-02 / FR-READ-04: a cloudy day does not look like dust."""
        reading = self.Reading.create({
            'site_id': self.t1.id, 'date': date(2026, 10, 1),
            'sun_hours': 2.0, 'actual_kwh': 760.00,
        })
        self.assertAlmostEqual(reading.expected_kwh, 800.00, places=2)
        self.assertAlmostEqual(reading.lost_kwh, 40.00, places=2)
        self.assertAlmostEqual(reading.loss_pct, 5.00, places=2)
        self.assertMoney(reading.lost_aed, 16.00)

    def test_ts03_no_negative_loss(self):
        """TS-03 / FR-READ-05: output above expected gives a loss of 0."""
        reading = self.Reading.create({
            'site_id': self.t1.id, 'date': date(2026, 10, 1),
            'sun_hours': 5.5, 'actual_kwh': 2250.00,
        })
        self.assertAlmostEqual(reading.lost_kwh, 0.0, places=2)
        self.assertAlmostEqual(reading.loss_pct, 0.0, places=2)
        self.assertMoney(reading.lost_aed, 0.0)

    def test_ts04_site_metrics_day_by_day(self):
        """TS-04: CAL-05 to CAL-13 against the table of section 5.2."""
        # day: running loss, % of trigger, status, current loss %,
        #      losing per day, clean due in (days)
        expected_rows = {
            1: (1.76, 0.12, 'green', 0.20, 1.76, 40),
            20: (369.60, 24.64, 'green', 3.80, 33.44, 21),
            34: (1047.20, 69.81, 'green', 6.60, 58.08, 7),
            35: (1108.80, 73.92, 'amber', 6.80, 59.84, 6),
            38: (1304.16, 86.94, 'amber', 7.40, 65.12, 3),
            40: (1443.20, 96.21, 'amber', 7.80, 68.64, 1),
            41: (1515.36, 101.02, 'red', 8.00, 70.40, 0),
        }
        site = self.t1
        for day in range(1, 42):
            self._load_day(site, day)
            if day not in expected_rows:
                continue
            running, trigger, status, loss_pct, per_day, due_in = expected_rows[day]
            label = 'day %s' % day
            self.assertMoney(site.running_loss, running, label)
            self.assertAlmostEqual(site.trigger_pct, trigger, places=2, msg=label)
            self.assertEqual(site.status, status, label)
            self.assertAlmostEqual(site.current_loss_pct, loss_pct, places=2, msg=label)
            self.assertMoney(site.avg_daily_loss, per_day, label)
            self.assertEqual(site.days_to_trigger, due_in, label)
            self.assertEqual(site.days_since_clean, day, label)
        # The other day-41 examples of section 5.2.
        self.assertAlmostEqual(site.running_loss_kwh, 3788.40, places=2)
        self.assertAlmostEqual(site.dust_rate_pct, 0.200, places=3)
        self.assertEqual(site.urgency_sequence, 1)
        self.assertEqual(site.last_reading_date, date(2026, 11, 10))
        self.assertMoney(site._projected_loss(1), 73.92)    # CAL-11
        self.assertMoney(site._projected_loss(7), 554.40)   # CAL-12

    def test_ts13_dust_storm(self):
        """TS-13: a storm brings the recommendation 12 days earlier."""
        site = self.t1
        self._load_days(site, 1, 20)
        for day in range(21, 30):
            self._load_day(site, day, extra_loss=0.10)
            if day == 21:
                self.assertMoney(site.running_loss, 494.56)
            if day == 25:
                self.assertMoney(site.running_loss, 1012.00)
            if day == 28:
                self.assertFalse(self._jobs(site), "no recommendation before day 29")
        job = self._jobs(site)
        self.assertEqual(len(job), 1)
        self.assertEqual(job.state, 'recommended')
        self.assertEqual(job.recommended_date, date(2026, 10, 29))
        self.assertMoney(job.trigger_running_loss, 1557.60)

    # ------------------------------------------------------------------
    # 11.2 Recommendation and explanation
    # ------------------------------------------------------------------
    def test_ts05_recommendation_created(self):
        """TS-05: one recommendation on day 41, nothing booked."""
        site = self.t1
        self._load_days(site, 1, 40)
        self.assertFalse(self._jobs(site), "no job after day 40")

        self._load_day(site, 41)
        job = self._jobs(site)
        self.assertEqual(len(job), 1)
        self.assertEqual(job.state, 'recommended')
        self.assertEqual(job.origin, 'auto')
        self.assertEqual(job.recommended_date, date(2026, 11, 10))
        self.assertFalse(job.crew_user_id)
        self.assertFalse(job.scheduled_date)
        self.assertEqual(job.manager_id, self.manager)
        self.assertMoney(job.cost, 1500.00)
        self.assertEqual(site.open_job_id, job)
        # The engine never changes the last-cleaned date (REC-05).
        self.assertEqual(site.last_cleaned_date, T1_LAST_CLEANED)
        # The site's manager has one To-Do, due today.
        todo = self._activities(job, const.REVIEW_SUMMARY)
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo.user_id, self.manager)
        self.assertEqual(todo.date_deadline, fields.Date.context_today(job))

    def test_ts06_snapshot_and_explanation(self):
        """TS-06: the numbers behind the job and the plain-language reason."""
        self._load_days(self.t1, 1, 41)
        job = self._jobs(self.t1)
        self.assertEqual(job.snapshot_date, date(2026, 11, 10))
        self.assertMoney(job.trigger_running_loss, 1515.36)
        self.assertMoney(job.trigger_cleaning_cost, 1500.00)
        self.assertAlmostEqual(job.trigger_pct, 101.02, places=2)
        self.assertEqual(job.trigger_days_since_clean, 41)
        self.assertEqual(job.trigger_last_cleaned_date, T1_LAST_CLEANED)
        self.assertAlmostEqual(job.trigger_loss_pct, 8.00, places=2)
        self.assertMoney(job.trigger_avg_daily_loss, 70.40)
        self.assertAlmostEqual(job.trigger_dust_rate_pct, 0.200, places=3)
        self.assertMoney(job.trigger_wait_cost, 554.40)

        # The explanation equals the T1 text of section 7.5...
        explanation = self._plain(job.explanation)
        for sentence in T1_EXPLANATION:
            self.assertIn(sentence, explanation)
        # ...and the same text is in the chatter and in the activity note.
        self.assertEqual(len(self._messages(job, T1_EXPLANATION[1])), 1)
        todo = self._activities(job, const.REVIEW_SUMMARY)
        for sentence in T1_EXPLANATION:
            self.assertIn(sentence, self._plain(todo.note))

    def test_ts07_refresh_then_freeze(self):
        """TS-07: figures stay live until Accept, then freeze (D4)."""
        site = self.t1
        self._load_days(site, 1, 41)
        job = self._jobs(site)

        # Evaluating twice with no new data changes nothing (REC-06).
        site.action_evaluate_now()
        site.action_evaluate_now()
        self.assertEqual(len(self._jobs(site)), 1)
        self.assertEqual(len(self._activities(job, const.REVIEW_SUMMARY)), 1)

        # Day 42 refreshes the same job; its recommended date stays.
        self._load_day(site, 42)
        self.assertEqual(self._jobs(site), job)
        self.assertMoney(job.trigger_running_loss, 1589.28)
        self.assertEqual(job.snapshot_date, date(2026, 11, 11))
        self.assertEqual(job.recommended_date, date(2026, 11, 10))

        # After Accept the snapshot no longer follows the site.
        job.action_accept()
        self._load_day(site, 43)
        self.assertMoney(job.trigger_running_loss, 1589.28)
        self.assertMoney(site.running_loss, 1664.96)

    def test_ts08_dismiss_and_snooze(self):
        """TS-08: a dismissal needs a reason and snoozes the site 7 days."""
        site = self.t1
        self._load_days(site, 1, 41)
        job = self._jobs(site)

        with self.assertRaises(UserError) as error:
            job.action_dismiss()
        self.assertIn("Enter a reason before dismissing.", str(error.exception))
        self.assertEqual(job.state, 'recommended')

        job.dismiss_reason = "Customer asked to wait"
        job.action_dismiss()
        self.assertEqual(job.state, 'dismissed')
        self.assertEqual(job.dismissed_date, date(2026, 11, 10))
        self.assertFalse(self._activities(job), "the review To-Do is gone")

        # Days 42 to 47: the as-of date is less than 7 days past the dismissal.
        self._load_days(site, 42, 47)
        self.assertEqual(len(self._jobs(site)), 1)

        # Day 48, 2026-11-17: a new recommendation.
        self._load_day(site, 48)
        jobs = self._jobs(site)
        self.assertEqual(len(jobs), 2)
        new_job = jobs[-1]
        self.assertEqual(new_job.state, 'recommended')
        self.assertEqual(new_job.recommended_date, date(2026, 11, 17))
        self.assertMoney(new_job.trigger_running_loss, 2069.76)

    # ------------------------------------------------------------------
    # 11.3 Job lifecycle, recovery and fault
    # ------------------------------------------------------------------
    def test_ts09_accept_and_mark_done(self):
        """TS-09: Accept, then Mark done resets the site's running loss."""
        site = self.t1
        self._load_days(site, 1, 41)
        job = self._jobs(site)
        tomorrow = fields.Date.context_today(job) + timedelta(days=1)

        job.crew_user_id = self.crew_user
        job.action_accept()
        self.assertEqual(job.state, 'scheduled')
        self.assertEqual(job.scheduled_date, tomorrow)
        self.assertFalse(self._activities(job, const.REVIEW_SUMMARY),
                         "the review To-Do is done")
        crew_todo = self._activities(job, "Clean T1")
        self.assertEqual(len(crew_todo), 1)
        self.assertEqual(crew_todo.user_id, self.crew_user)
        self.assertEqual(crew_todo.date_deadline, tomorrow)

        # A clean dated on or before the last clean is refused (WF-05).
        job.date_done = T1_LAST_CLEANED
        with self.assertRaises(UserError):
            job.action_done()
        self.assertEqual(job.state, 'scheduled')

        job.date_done = date(2026, 11, 11)
        job.action_done()
        self.assertEqual(job.state, 'done')
        self.assertEqual(job.recovery_state, 'pending')
        self.assertFalse(self._activities(job), "open activities are done")
        self.assertEqual(site.last_cleaned_date, date(2026, 11, 11))
        self.assertMoney(site.running_loss, 0.0)
        self.assertAlmostEqual(site.trigger_pct, 0.0, places=2)
        self.assertEqual(site.status, 'green')
        self.assertFalse(site.open_job_id)
        self.assertEqual(len(self._messages(site, "Cleaned on 11 Nov 2026")), 1)

        # Done is final (WF-08).
        with self.assertRaises(UserError):
            job.action_accept()
        job.dismiss_reason = "Too late"
        with self.assertRaises(UserError):
            job.action_dismiss()

    def test_ts10_recovery_confirmed(self):
        """TS-10: recovery and payback after three readings (CAL-15)."""
        site = self.t1
        job = self._recommend_and_clean_t1()
        after = [
            (date(2026, 11, 12), 2195.60),
            (date(2026, 11, 13), 2191.20),
            (date(2026, 11, 14), 2186.80),
        ]
        for index, (day, actual) in enumerate(after):
            self.Reading.create({
                'site_id': site.id, 'date': day, 'sun_hours': 5.5, 'actual_kwh': actual,
            })
            if index == 1:
                self.assertEqual(job.recovery_state, 'pending',
                                 "still awaiting readings after the second one")

        self.assertEqual(job.recovery_state, 'confirmed')
        self.assertMoney(job.loss_before_per_day, 70.40)
        self.assertMoney(job.loss_after_per_day, 3.52)
        self.assertAlmostEqual(job.loss_pct_before, 8.00, places=2)
        self.assertAlmostEqual(job.loss_pct_after, 0.40, places=2)
        self.assertMoney(job.recovery_per_day, 66.88)
        self.assertAlmostEqual(job.recovery_pct, 95.0, places=1)
        self.assertAlmostEqual(job.payback_days, 22.4, places=1)
        self.assertFalse(site.fault_suspected)
        self.assertEqual(len(self._messages(
            job,
            "Clean confirmed: loss fell from AED 70.40/day to AED 3.52/day. "
            "The AED 1,500 clean pays for itself in 22.4 days.")), 1)
        self.assertMoney(site.running_loss, 10.56)

        # A stored result never changes afterwards (FR-RCV-05).
        self.Reading.create({
            'site_id': site.id, 'date': date(2026, 11, 15),
            'sun_hours': 5.5, 'actual_kwh': 2000.00,
        })
        self.assertMoney(job.loss_after_per_day, 3.52)
        self.assertEqual(job.recovery_state, 'confirmed')

    def test_ts11_fault_flag(self):
        """TS-11: no recovery flags the site and blocks recommendations."""
        site = self.t1
        job = self._recommend_and_clean_t1()
        for offset in range(23):
            self.Reading.create({
                'site_id': site.id,
                'date': date(2026, 11, 12) + timedelta(days=offset),
                'sun_hours': 5.5,
                'actual_kwh': 2024.00,
            })
            if offset == 2:
                self.assertEqual(job.recovery_state, 'fault')
                self.assertMoney(job.loss_before_per_day, 70.40)
                self.assertMoney(job.loss_after_per_day, 70.40)
                self.assertMoney(job.recovery_per_day, 0.0)
                self.assertAlmostEqual(job.recovery_pct, 0.0, places=1)
                self.assertAlmostEqual(job.payback_days, 0.0, places=1)
                self.assertTrue(site.fault_suspected)
                self.assertEqual(
                    len(self._activities(site, const.INSPECTION_SUMMARY)), 1)

        # Over the trigger, yet no recommendation while flagged (FR-FAU-02).
        self.assertMoney(site.running_loss, 1619.20)
        self.assertEqual(len(self._jobs(site)), 1)

        site.action_mark_inspected()
        self.assertFalse(site.fault_suspected)
        self.assertEqual(job.recovery_state, 'fault', "the job keeps its result")
        site.action_evaluate_now()
        jobs = self._jobs(site)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[-1].state, 'recommended')

    # ------------------------------------------------------------------
    # 11.4 Simulator and fleet
    # ------------------------------------------------------------------
    def test_ts12_simulator(self):
        """TS-12: CAL-14 against the table of section 5.3."""
        site = self.t1
        # day: extra loss W, clean now total, per day, wait total, per day,
        #      verdict, saving per day, saving per year, clean due in
        expected_rows = {
            20: (295.68, 1869.60, 93.48, 2165.28, 80.20, 'wait', 13.28, 4849, 21),
            38: (517.44, 2804.16, 73.79, 3321.60, 73.81, 'clean_now', 0.02, 7, 3),
            41: (554.40, 3015.36, 73.55, 3569.76, 74.37, 'clean_now', 0.82, 301, 0),
        }
        expected_texts = {
            20: "Wait. Cleaning in 7 days brings this cycle's cost down from AED "
                "93.48/day to AED 80.20/day, about AED 4,849 a year, even after "
                "losing about AED 296 more electricity.",
            41: "Clean now. Waiting 7 days would lose about AED 554 more "
                "electricity and raise this cycle's cost from AED 73.55/day to "
                "AED 74.37/day, about AED 301 a year.",
        }
        for day in range(1, 42):
            self._load_day(site, day)
            if day == 5:
                simulator = self._simulate(site)
                self.assertEqual(simulator.verdict, 'wait')
                self.assertTrue(simulator.uses_default_rate,
                                "the default-rate note shows on day 5")
            if day not in expected_rows:
                continue
            (extra, now_total, now_per_day, wait_total, wait_per_day,
             verdict, saving_day, saving_year, due_in) = expected_rows[day]
            label = 'day %s' % day
            jobs_before = len(self._jobs(site))
            running_before = site.running_loss

            simulator = self._simulate(site)
            self.assertFalse(simulator.uses_default_rate, label)
            self.assertEqual(simulator.now_cycle_days, day, label)
            self.assertEqual(simulator.wait_cycle_days, day + 7, label)
            self.assertMoney(simulator.extra_loss_if_wait, extra, label)
            self.assertMoney(simulator.now_electricity_loss, site.running_loss, label)
            self.assertMoney(simulator.wait_electricity_loss, site.running_loss + extra, label)
            self.assertMoney(simulator.now_cleaning_cost, 1500.00, label)
            self.assertMoney(simulator.wait_cleaning_cost, 1500.00, label)
            self.assertMoney(simulator.now_total, now_total, label)
            self.assertMoney(simulator.now_cost_per_day, now_per_day, label)
            self.assertMoney(simulator.wait_total, wait_total, label)
            self.assertMoney(simulator.wait_cost_per_day, wait_per_day, label)
            self.assertEqual(simulator.verdict, verdict, label)
            self.assertMoney(simulator.saving_per_day, saving_day, label)
            self.assertEqual(round(simulator.saving_per_year), saving_year, label)
            self.assertEqual(simulator.days_to_trigger, due_in, label)
            if day in expected_texts:
                self.assertEqual(simulator.verdict_text, expected_texts[day], label)

            # The simulator changes no record (FR-SIM-05).
            self.assertEqual(len(self._jobs(site)), jobs_before, label)
            self.assertMoney(site.running_loss, running_before, label)

    def test_ts14_fleet_priority(self):
        """TS-14: colour first, then money lost per day (FR-FLT-02)."""
        site_x = self.t1
        site_x.name = 'X'
        site_y = self._new_site('Y', capacity=1000.0, cleaning_cost=3000.0)
        site_z = self._new_site('Z', capacity=250.0, cleaning_cost=750.0)
        site_g = self._new_site('G')
        self._load_days(site_x, 1, 41)
        self._load_days(site_y, 1, 41)
        self._load_days(site_z, 1, 36)
        self._load_days(site_g, 1, 10)

        sites = site_x | site_y | site_z | site_g
        fleet = self.Site.search([('id', 'in', sites.ids)])   # default order
        self.assertEqual(fleet.mapped('name'), ['Y', 'X', 'Z', 'G'])

        self.assertEqual(site_y.status, 'red')
        self.assertMoney(site_y.avg_daily_loss, 140.80)
        self.assertEqual(site_x.status, 'red')
        self.assertMoney(site_x.avg_daily_loss, 70.40)
        self.assertEqual(site_z.status, 'amber')
        self.assertAlmostEqual(site_z.trigger_pct, 78.14, places=2)
        self.assertMoney(site_z.avg_daily_loss, 30.80)
        self.assertEqual(site_g.status, 'green')
        self.assertMoney(site_g.avg_daily_loss, 15.84)

        # The list footer totals (FR-FLT-05).
        self.assertMoney(sum(fleet.mapped('running_loss')), 5228.96)
        self.assertMoney(sum(fleet.mapped('avg_daily_loss')), 257.84)
