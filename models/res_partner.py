# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class Partner(models.Model):
    _inherit = 'res.partner'

    # Music Industry Flags
    is_artist = fields.Boolean(string='Is Artist', default=False)
    is_writer = fields.Boolean(string='Is Writer/Composer', default=False)
    is_producer = fields.Boolean(string='Is Producer', default=False)
    is_engineer = fields.Boolean(string='Is Engineer', default=False)
    is_label_vendor = fields.Boolean(string='Is Label Vendor', default=False)
    is_distributor = fields.Boolean(string='Is Distributor', default=False)
    is_pro = fields.Boolean(string='Is Performing Rights Organization', default=False)
    is_studio_client = fields.Boolean(string='Is Studio Client', default=False)

    # Banking & Payment Information
    bank_account_number = fields.Char(string='Bank Account Number')
    bank_routing_number = fields.Char(string='Bank Routing Number')
    iban = fields.Char(string='IBAN')
    swift_bic = fields.Char(string='SWIFT/BIC')
    preferred_payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('wire', 'Wire Transfer'),
        ('check', 'Check'),
        ('paypal', 'PayPal'),
        ('digital_wallet', 'Digital Wallet')
    ], string='Preferred Payment Method', default='bank_transfer')

    # Tax Information
    tax_id_number = fields.Char(string='Tax ID Number')
    ssn_last_four = fields.Char(string='SSN Last 4 Digits', size=4)
    w9_on_file = fields.Boolean(string='W-9 on File', default=False)
    w8_on_file = fields.Boolean(string='W-8 on File', default=False)
    tax_withholding_rate = fields.Float(string='Tax Withholding Rate (%)', default=0.0)

    # PRO Affiliations
    primary_pro = fields.Selection([
        ('ascap', 'ASCAP'),
        ('bmi', 'BMI'),
        ('sesac', 'SESAC'),
        ('socan', 'SOCAN'),
        ('prs', 'PRS for Music'),
        ('gema', 'GEMA'),
        ('sacem', 'SACEM'),
        ('sabam', 'SABAM'),
        ('siae', 'SIAE'),
        ('sgae', 'SGAE'),
        ('other', 'Other')
    ], string='Primary PRO')
    
    secondary_pro = fields.Selection([
        ('ascap', 'ASCAP'),
        ('bmi', 'BMI'),
        ('sesac', 'SESAC'),
        ('socan', 'SOCAN'),
        ('prs', 'PRS for Music'),
        ('gema', 'GEMA'),
        ('sacem', 'SACEM'),
        ('sabam', 'SABAM'),
        ('siae', 'SIAE'),
        ('sgae', 'SGAE'),
        ('other', 'Other')
    ], string='Secondary PRO')

    ipi_number = fields.Char(string='IPI Number', help='Interested Parties Information Number')
    cae_number = fields.Char(string='CAE Number', help='Compositeur, Auteur et Editeur Number')
    
    # Portal & Communication
    portal_access_granted = fields.Boolean(string='Portal Access Granted', default=False)
    portal_onboarding_complete = fields.Boolean(string='Portal Onboarding Complete', default=False)
    signature_image = fields.Binary(string='Digital Signature')
    
    # Royalty Settings
    default_royalty_withholding = fields.Float(string='Default Royalty Withholding (%)', default=0.0)
    minimum_payment_threshold = fields.Monetary(string='Minimum Payment Threshold', default=25.0)
    
    # Social Media & Promotion
    spotify_artist_id = fields.Char(string='Spotify Artist ID')
    apple_music_artist_id = fields.Char(string='Apple Music Artist ID')
    youtube_channel_id = fields.Char(string='YouTube Channel ID')
    instagram_handle = fields.Char(string='Instagram Handle')
    twitter_handle = fields.Char(string='Twitter Handle')
    tiktok_handle = fields.Char(string='TikTok Handle')
    
    # Artist/Writer Specific
    stage_name = fields.Char(string='Stage/Professional Name')
    genre_ids = fields.Many2many('music.genre', string='Genres')
    birth_date = fields.Date(string='Date of Birth')
    birth_place = fields.Char(string='Place of Birth')
    
    # Studio Specific
    studio_hourly_rate = fields.Monetary(string='Studio Hourly Rate')
    studio_day_rate = fields.Monetary(string='Studio Day Rate')
    studio_specialties = fields.Text(string='Studio Specialties')
    
    # Counts for Smart Buttons
    deal_count = fields.Integer(string='Deals Count', compute='_compute_deal_count')
    royalty_statement_count = fields.Integer(string='Royalty Statements Count', compute='_compute_royalty_statement_count')
    booking_count = fields.Integer(string='Bookings Count', compute='_compute_booking_count')
    work_count = fields.Integer(string='Works Count', compute='_compute_work_count')
    recording_count = fields.Integer(string='Recordings Count', compute='_compute_recording_count')

    @api.depends('id')
    def _compute_deal_count(self):
        for partner in self:
            partner.deal_count = self.env['label.deal'].search_count([('party_id', '=', partner.id)])

    @api.depends('id')
    def _compute_royalty_statement_count(self):
        for partner in self:
            partner.royalty_statement_count = self.env['royalty.statement'].search_count([('partner_id', '=', partner.id)])

    @api.depends('id')
    def _compute_booking_count(self):
        for partner in self:
            partner.booking_count = self.env['studio.booking'].search_count([('client_id', '=', partner.id)])

    @api.depends('id')
    def _compute_work_count(self):
        for partner in self:
            # Count works where this partner is a writer/composer
            partner.work_count = self.env['music.work'].search_count([('composer_ids', 'in', partner.id)])

    @api.depends('id')
    def _compute_recording_count(self):
        for partner in self:
            # Count recordings where this partner is the main artist
            partner.recording_count = self.env['music.recording'].search_count([('main_artist_ids', 'in', partner.id)])

    @api.constrains('ipi_number')
    def _check_ipi_number(self):
        """Validate IPI number format"""
        for partner in self:
            if partner.ipi_number and not re.match(r'^\d{11}$', partner.ipi_number):
                raise ValidationError(_('IPI number must be exactly 11 digits.'))
    
    @api.constrains('cae_number')
    def _check_cae_number(self):
        """Validate CAE number format"""
        for partner in self:
            if partner.cae_number and not re.match(r'^\d{9}$', partner.cae_number):
                raise ValidationError(_('CAE number must be exactly 9 digits.'))
    
    @api.constrains('ssn_last_four')
    def _check_ssn_last_four(self):
        """Validate SSN last 4 digits"""
        for partner in self:
            if partner.ssn_last_four and not re.match(r'^\d{4}$', partner.ssn_last_four):
                raise ValidationError(_('SSN last 4 digits must be exactly 4 digits.'))

    def action_view_deals(self):
        """Smart button action to view related deals"""
        return {
            'name': _('Deals'),
            'type': 'ir.actions.act_window',
            'res_model': 'label.deal',
            'view_mode': 'tree,form',
            'domain': [('party_id', '=', self.id)],
            'context': {'default_party_id': self.id},
        }

    def action_view_royalty_statements(self):
        """Smart button action to view royalty statements"""
        return {
            'name': _('Royalty Statements'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.statement',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_bookings(self):
        """Smart button action to view studio bookings"""
        return {
            'name': _('Studio Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'studio.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def action_view_works(self):
        """Smart button action to view related works"""
        return {
            'name': _('Works'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.work',
            'view_mode': 'tree,form',
            'domain': [('composer_ids', 'in', self.id)],
        }

    def action_view_recordings(self):
        """Smart button action to view related recordings"""
        return {
            'name': _('Recordings'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.recording',
            'view_mode': 'tree,form',
            'domain': [('main_artist_ids', 'in', self.id)],
        }