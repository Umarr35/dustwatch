# -*- coding: utf-8 -*-
{
    'name': 'DustWatch',
    'version': '19.0.1.0.0',
    'category': 'Operations',
    'summary': 'Solar panel cleaning recommendations based on the money lost to dust',
    'description': """
DustWatch
=========
For each solar rooftop, DustWatch tracks how much money dust has cost since
the last clean. It recommends a clean on the day cleaning becomes cheaper
than waiting, and proves afterwards whether the clean paid off.

* Fleet priority: every site ranked by urgency and money lost per day
* Explainable cleaning recommendations (never booked automatically)
* Clean Now vs Wait simulator
* Recovery, payback and fault detection after each clean
""",
    'author': 'Muhammad Umar Rizwan',
    'license': 'LGPL-3',

    # ARC-01: only Contacts and Discuss on top of the base framework.
    'depends': ['base', 'web', 'mail', 'contacts'],

    # ARC-03: the load order matters. Groups come first because access rights,
    # views and menus refer to them; sample data comes last because it needs
    # the models, the sequence and the views to exist.
    'data': [
        # 1. security groups, 2. access rights
        'security/dustwatch_security.xml',
        'security/ir.model.access.csv',
        # 3. sequence, 4. scheduled action
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        # 5. views
        'views/dustwatch_site_views.xml',
        'views/dustwatch_reading_views.xml',
        'views/dustwatch_cleaning_job_views.xml',
        'views/res_partner_views.xml',
        # 6. dialog view
        'wizard/dustwatch_simulator_views.xml',
        # 7. menus
        'views/dustwatch_menus.xml',
        # 8. sample sites, 9. historic jobs, 10. readings (DAT-01: module
        #    data, not demo data, so it loads on every install)
        'data/dustwatch_sample_sites.xml',
        'data/dustwatch.cleaning.job.csv',
        'data/dustwatch.reading.csv',
        # 11. post-load: one evaluation after everything is in place
        'data/dustwatch_post_load.xml',
    ],

    # The output chart of the site page (FR-CHT-01). Chart.js itself is the
    # copy bundled with Odoo and is loaded on demand by the component.
    'assets': {
        'web.assets_backend': [
            'dustwatch/static/src/output_chart/output_chart.js',
            'dustwatch/static/src/output_chart/output_chart.xml',
        ],
    },

    'installable': True,
    'application': True,
}