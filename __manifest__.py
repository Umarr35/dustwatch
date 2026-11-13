# -*- coding: utf-8 -*-
{
    'name': 'DustWatch - Autonomous Solar Soiling & Cleaning Optimizer',
    'version': '19.0.1.0.0',
    'category': 'Operations/Renewable Energy',
    'summary': 'Calculates solar soiling financial losses and automatically triggers cleaning at breakeven.',
    'description': """
DustWatch: Odoo Hackathon 2026 (Green & Renewable Energy Track)
==============================================================
An intelligent operations and financial decision engine for solar panel installations in arid desert climates:
- Quantifies daily electricity output loss due to dust accumulation.
- Converts physical generation deficits (kWh) into local currency (AED).
- Programmatically dispatches cleaning work orders when cumulative loss reaches the cost of one clean.
- Measures post-clean recovery to verify ROI and diagnose equipment faults.
- Designed as both a modular add-on for existing solar contractors and a turnkey operations platform.
    """,
    'author': 'DustWatch Engineering Team',
    'website': 'https://github.com/Umarr35/dustwatch',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/sample_demo_data.xml',
        'wizards/import_readings_views.xml',
        'views/site_views.xml',
        'views/reading_views.xml',
        'views/job_views.xml',
        'views/res_partner_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,
}
