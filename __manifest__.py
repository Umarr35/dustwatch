
{
    'name': 'DustWatch',
    'version': '1.0',
    'category': 'Operations',
    'summary': 'Dust monitoring and management',
    'depends': ['base', 'web'],

    'data': [
        'views/dustwatch_menu.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'dustwatch/static/src/js/dustwatch_home.js',
            'dustwatch/static/src/xml/dustwatch_home.xml',
        ],
    },

    'installable': True,
    'application': True,
}
