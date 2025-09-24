# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Statutory Rates
    us_mechanical_rate = fields.Float(
        string='US Mechanical Rate (per track)',
        default=0.091,
        config_parameter='label_studio_publishing.us_mechanical_rate',
        help='Current US statutory mechanical royalty rate per track'
    )
    
    ca_mechanical_rate = fields.Float(
        string='Canada Mechanical Rate (per track)',
        default=0.081,
        config_parameter='label_studio_publishing.ca_mechanical_rate',
        help='Current Canadian mechanical royalty rate per track'
    )

    # Reserve Settings
    default_reserve_percentage = fields.Float(
        string='Default Reserve Percentage',
        default=15.0,
        config_parameter='label_studio_publishing.default_reserve_percentage',
        help='Default percentage of royalties to hold in reserves'
    )
    
    default_reserve_release_months = fields.Integer(
        string='Default Reserve Release Period (months)',
        default=12,
        config_parameter='label_studio_publishing.default_reserve_release_months',
        help='Default number of months to hold reserves before release'
    )

    # Payment Settings
    minimum_payment_threshold = fields.Float(
        string='Minimum Payment Threshold',
        default=25.0,
        config_parameter='label_studio_publishing.minimum_payment_threshold',
        help='Minimum amount required before issuing payments'
    )
    
    enable_negative_statements = fields.Boolean(
        string='Enable Negative Statements',
        default=True,
        config_parameter='label_studio_publishing.enable_negative_statements',
        help='Allow negative balances on royalty statements'
    )

    # Cross-Collateralization
    enable_cross_collateralization = fields.Boolean(
        string='Enable Cross-Collateralization by Default',
        default=False,
        config_parameter='label_studio_publishing.enable_cross_collateralization',
        help='Enable cross-collateralization between releases by default'
    )

    # Matching Engine Settings
    matching_confidence_threshold = fields.Float(
        string='Auto-Matching Confidence Threshold',
        default=0.85,
        config_parameter='label_studio_publishing.matching_confidence_threshold',
        help='Minimum confidence score for automatic matching (0.0 - 1.0)'
    )
    
    fuzzy_matching_threshold = fields.Float(
        string='Fuzzy Matching Threshold',
        default=0.7,
        config_parameter='label_studio_publishing.fuzzy_matching_threshold',
        help='Threshold for fuzzy string matching (0.0 - 1.0)'
    )

    # File Import Settings
    max_import_batch_size = fields.Integer(
        string='Maximum Import Batch Size',
        default=10000,
        config_parameter='label_studio_publishing.max_import_batch_size',
        help='Maximum number of lines to process in a single import batch'
    )

    # Studio Settings
    studio_default_deposit_percentage = fields.Float(
        string='Studio Default Deposit Percentage',
        default=50.0,
        config_parameter='label_studio_publishing.studio_default_deposit_percentage',
        help='Default deposit percentage for studio bookings'
    )
    
    studio_cancellation_hours = fields.Integer(
        string='Studio Cancellation Policy (hours)',
        default=24,
        config_parameter='label_studio_publishing.studio_cancellation_hours',
        help='Minimum hours notice required for booking cancellation'
    )

    # Notification Settings
    enable_email_notifications = fields.Boolean(
        string='Enable Email Notifications',
        default=True,
        config_parameter='label_studio_publishing.enable_email_notifications',
        help='Send email notifications for statements, bookings, etc.'
    )
    
    enable_sms_notifications = fields.Boolean(
        string='Enable SMS Notifications',
        default=False,
        config_parameter='label_studio_publishing.enable_sms_notifications',
        help='Send SMS notifications (requires Twilio configuration)'
    )
    
    # Twilio Settings (for SMS)
    twilio_account_sid = fields.Char(
        string='Twilio Account SID',
        config_parameter='label_studio_publishing.twilio_account_sid'
    )
    
    twilio_auth_token = fields.Char(
        string='Twilio Auth Token',
        config_parameter='label_studio_publishing.twilio_auth_token',
        password=True
    )
    
    twilio_from_number = fields.Char(
        string='Twilio From Number',
        config_parameter='label_studio_publishing.twilio_from_number',
        help='Twilio phone number to send SMS from'
    )

    # DDEX Settings
    ddex_party_id = fields.Char(
        string='DDEX Party ID',
        config_parameter='label_studio_publishing.ddex_party_id',
        help='Your DDEX Party Identifier'
    )
    
    ddex_message_thread_id = fields.Char(
        string='DDEX Message Thread ID Prefix',
        default='LSP',
        config_parameter='label_studio_publishing.ddex_message_thread_id',
        help='Prefix for DDEX message thread IDs'
    )

    # Document Storage
    default_document_folder_structure = fields.Selection([
        ('artist', 'By Artist'),
        ('release', 'By Release'),
        ('date', 'By Date'),
        ('type', 'By Document Type')
    ], string='Default Document Folder Structure',
       default='artist',
       config_parameter='label_studio_publishing.default_document_folder_structure',
       help='How to organize uploaded documents')

    # Accounting Integration
    royalty_payable_account_id = fields.Many2one(
        'account.account',
        string='Royalty Payable Account',
        config_parameter='label_studio_publishing.royalty_payable_account_id',
        help='Default account for royalty payables'
    )
    
    advance_payable_account_id = fields.Many2one(
        'account.account',
        string='Advance Payable Account', 
        config_parameter='label_studio_publishing.advance_payable_account_id',
        help='Default account for advance payables'
    )
    
    reserve_liability_account_id = fields.Many2one(
        'account.account',
        string='Reserve Liability Account',
        config_parameter='label_studio_publishing.reserve_liability_account_id',
        help='Default account for reserve liabilities'
    )

    @api.constrains('matching_confidence_threshold', 'fuzzy_matching_threshold')
    def _check_threshold_values(self):
        """Validate threshold values are between 0 and 1"""
        for record in self:
            if not (0 <= record.matching_confidence_threshold <= 1):
                raise ValidationError(_('Matching confidence threshold must be between 0.0 and 1.0'))
            if not (0 <= record.fuzzy_matching_threshold <= 1):
                raise ValidationError(_('Fuzzy matching threshold must be between 0.0 and 1.0'))

    @api.constrains('default_reserve_percentage')
    def _check_reserve_percentage(self):
        """Validate reserve percentage is reasonable"""
        for record in self:
            if not (0 <= record.default_reserve_percentage <= 100):
                raise ValidationError(_('Reserve percentage must be between 0% and 100%'))

    @api.constrains('studio_default_deposit_percentage')
    def _check_deposit_percentage(self):
        """Validate deposit percentage is reasonable"""
        for record in self:
            if not (0 <= record.studio_default_deposit_percentage <= 100):
                raise ValidationError(_('Deposit percentage must be between 0% and 100%'))