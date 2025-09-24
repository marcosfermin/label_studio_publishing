# -*- coding: utf-8 -*-
{
    'name': 'Label Studio Publishing',
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'summary': 'Complete Record Label, Recording Studio & Music Publishing Management',
    'description': """
        Production-ready Odoo 19 module for music industry operations:
        
        * Record Label: A&R pipeline, artist deals, releases, distribution, royalty accounting
        * Recording Studio: Room & engineer scheduling, session management, equipment tracking
        * Music Publishing: Song registrations, splits, PRO management, sync licensing
        * Unified Royalty Engine: Statement imports, matching, recoupment, payouts
        * Artist/Writer/Producer Portals: Statements, approvals, bookings
        * Full Accounting Integration: Multi-currency, multi-company support
    """,
    'author': 'Contaura LLC',
    'website': 'https://www.contaura.com',
    'depends': [
        'base',
        'contacts',
        'mail',
        'calendar',
        'hr',
        'stock',
        'sale_management',
        'purchase',
        'account',
        'account_accountant',
        'documents',
        'website',
        'portal',
        'utm',
        'resource',
        'hr_timesheet',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/portal_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/mail_template_data.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/res_country_data.xml',
        'data/product_data.xml',
        
        # Views - Core
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        
        # Views - Label
        'views/label_anr_lead_views.xml',
        'views/label_deal_views.xml',
        'views/music_work_views.xml',
        'views/music_recording_views.xml',
        'views/music_release_views.xml',
        'views/music_rights_views.xml',
        
        # Views - Studio
        'views/studio_room_views.xml',
        'views/studio_equipment_views.xml',
        'views/studio_booking_views.xml',
        'views/studio_session_views.xml',
        
        # Views - Publishing
        'views/publ_registration_views.xml',
        'views/publ_split_views.xml',
        'views/sync_license_views.xml',
        'views/dist_partner_views.xml',
        
        # Views - Royalty Engine
        'views/royalty_usage_line_views.xml',
        'views/royalty_rule_views.xml',
        'views/royalty_recoup_ledger_views.xml',
        'views/royalty_statement_views.xml',
        'views/royalty_payment_views.xml',
        
        # Wizards
        'views/import_export_wizard_views.xml',
        'wizards/royalty_statement_import_views.xml',
        'wizards/royalty_statement_generate_views.xml',
        'wizards/ddex_export_wizard_views.xml',
        'wizards/reserve_release_wizard_views.xml',
        
        # Reports
        'reports/royalty_statement_template.xml',
        'reports/booking_confirmation_template.xml',
        'reports/remittance_advice_template.xml',
        
        # Menus
        'views/menu_views.xml',
        
        # Portal
        'views/portal_templates.xml',
        'views/portal_studio_templates.xml',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
        'demo/music_catalog_demo.xml',
        'demo/label_deals_demo.xml',
        'demo/studio_demo.xml',
        'demo/royalty_demo.xml',
        'demo/publishing_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'label_studio_publishing/static/src/js/*.js',
            'label_studio_publishing/static/src/css/*.css',
        ],
        'web.assets_frontend': [
            'label_studio_publishing/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    'price': 0,
    'currency': 'USD',
}