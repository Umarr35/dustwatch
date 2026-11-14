# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ResPartner(models.Model):
    """Customer: the two fields behind the "Solar sites" smart button
    (specification section 4.5, DM-P-01). No other core model is changed."""
    _inherit = 'res.partner'

    dustwatch_site_ids = fields.One2many(
        'dustwatch.site', 'partner_id', string='Solar sites',
    )
    # The Python label differs from the one2many label so Odoo does not log
    # a "same label" warning (NFR-01); the button itself shows "Solar sites".
    dustwatch_site_count = fields.Integer(
        string='Number of solar sites', compute='_compute_dustwatch_site_count',
    )

    @api.depends('dustwatch_site_ids')
    def _compute_dustwatch_site_count(self):
        # Counted with superuser rights: a contact page must open for every
        # user, including users who cannot read DustWatch sites.
        for partner in self:
            partner.dustwatch_site_count = len(partner.sudo().dustwatch_site_ids)

    def action_view_dustwatch_sites(self):
        """Smart button "Solar sites" (FR-SITE-06, UI-08): the fleet
        priority screen filtered to this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Solar sites"),
            'res_model': 'dustwatch.site',
            'view_mode': 'list,kanban,graph,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_dustwatch_map(self):
        """Open this customer's sites in the live map."""
        self.ensure_one()
        partner = self.commercial_partner_id
        action = self.env.ref('dustwatch.action_dustwatch_live_map').read()[0]
        action['context'] = {'dustwatch_partner_id': partner.id}
        return action
