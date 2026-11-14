# -*- coding: utf-8 -*-
from odoo import _, fields, models


class CrmLead(models.Model):
    """Expose a CRM opportunity's customer's solar fleet to DustWatch."""

    _inherit = 'crm.lead'

    dustwatch_site_count = fields.Integer(
        string='Solar sites',
        related='partner_id.commercial_partner_id.dustwatch_site_count',
        readonly=True,
    )

    def action_view_dustwatch_sites(self):
        self.ensure_one()
        if not self.partner_id:
            return False
        partner = self.partner_id.commercial_partner_id
        action = partner.action_view_dustwatch_sites()
        action['name'] = _('Solar sites for %s') % partner.display_name
        return action

    def action_open_dustwatch_map(self):
        """Open the CRM customer's sites in the live DustWatch map."""
        self.ensure_one()
        if not self.partner_id:
            return False
        partner = self.partner_id.commercial_partner_id
        action = self.env.ref('dustwatch.action_dustwatch_live_map').read()[0]
        action['context'] = {'dustwatch_partner_id': partner.id}
        return action
