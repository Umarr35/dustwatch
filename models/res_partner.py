# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    dustwatch_site_ids = fields.One2many('dustwatch.site', 'partner_id', string='Solar Sites')
    dustwatch_site_count = fields.Integer(string='Solar Sites Count', compute='_compute_dustwatch_metrics')
    dustwatch_total_capacity_kwp = fields.Float(string='Total Solar Capacity (kWp)', compute='_compute_dustwatch_metrics')
    dustwatch_total_saved_aed = fields.Float(string='Total DustWatch Savings (AED)', compute='_compute_dustwatch_metrics')

    @api.depends('dustwatch_site_ids', 'dustwatch_site_ids.capacity_kwp', 'dustwatch_site_ids.lifetime_saved_aed')
    def _compute_dustwatch_metrics(self):
        for partner in self:
            sites = partner.dustwatch_site_ids
            partner.dustwatch_site_count = len(sites)
            partner.dustwatch_total_capacity_kwp = sum(sites.mapped('capacity_kwp'))
            partner.dustwatch_total_saved_aed = sum(sites.mapped('lifetime_saved_aed'))

    def action_view_dustwatch_sites(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Solar Sites: %s') % self.name,
            'res_model': 'dustwatch.site',
            'view_mode': 'kanban,list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
