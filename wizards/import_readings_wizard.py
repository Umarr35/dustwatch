# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DustwatchImportReadingsWizard(models.TransientModel):
    _name = 'dustwatch.import.readings.wizard'
    _description = 'Import Daily Solar Telemetry from CSV'

    site_id = fields.Many2one('dustwatch.site', string='Target Rooftop Site', required=True)
    file_data = fields.Binary(string='Telemetry CSV File', required=True)
    file_name = fields.Char(string='Filename')

    def action_import_csv(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please upload a CSV file."))

        try:
            decoded = base64.b64decode(self.file_data).decode('utf-8')
        except Exception:
            raise UserError(_("Could not decode file. Please ensure it is standard UTF-8 CSV."))

        csv_reader = csv.DictReader(io.StringIO(decoded))
        readings_to_create = []

        count = 0
        for row in csv_reader:
            date_val = row.get('date', '').strip()
            sun_hours = float(row.get('sun_hours', 5.5))
            actual_kwh = float(row.get('actual_kwh', 0.0))
            notes = row.get('notes', '')

            readings_to_create.append({
                'site_id': self.site_id.id,
                'date': date_val,
                'sun_hours': sun_hours,
                'actual_kwh': actual_kwh,
                'notes': notes,
            })
            count += 1

        if readings_to_create:
            self.env['dustwatch.reading'].create(readings_to_create)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Telemetry Import Completed'),
                'message': _('Successfully ingested %d daily readings into %s.') % (count, self.site_id.name),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
