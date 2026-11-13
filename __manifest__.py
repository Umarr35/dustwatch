{
    'name': 'DustWatch',
    'summary': 'DustWatch application',
    'version': '1.0',
    'category': 'Productivity',
    'depends': ['base'],
    'application': True,
    'installable': True,
    'data': [],
    'assets': {
        'web.assets_backend': [
            'dustwatch/static/src/js/dustwatch_home.js',
            'dustwatch/static/src/xml/dustwatch_home.xml',
        ],
    },
    'license': 'LGPL-3',
}
