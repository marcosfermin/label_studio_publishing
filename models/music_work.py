# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class MusicGenre(models.Model):
    _name = 'music.genre'
    _description = 'Music Genre'
    _order = 'name'

    name = fields.Char(string='Genre Name', required=True, translate=True)
    parent_id = fields.Many2one('music.genre', string='Parent Genre')
    child_ids = fields.One2many('music.genre', 'parent_id', string='Sub-genres')
    color = fields.Integer(string='Color', default=0)
    active = fields.Boolean(string='Active', default=True)


class MusicWork(models.Model):
    _name = 'music.work'
    _description = 'Musical Work (Composition)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'title'

    # Basic Information
    title = fields.Char(string='Title', required=True, tracking=True, index=True)
    alternate_titles = fields.Text(string='Alternate Titles', 
                                  help='Alternative titles, one per line')
    subtitle = fields.Char(string='Subtitle')
    
    # Identification
    iswc = fields.Char(string='ISWC', help='International Standard Musical Work Code',
                       index=True)
    internal_work_id = fields.Char(string='Internal Work ID', required=True, copy=False,
                                  default=lambda self: _('New'))
    
    # Creation Details
    original_pub_date = fields.Date(string='Original Publication Date')
    creation_date = fields.Date(string='Creation Date')
    duration_seconds = fields.Integer(string='Duration (seconds)')
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display', store=True)
    
    # Classification
    genre_ids = fields.Many2many('music.genre', string='Genres')
    language = fields.Char(string='Language', default='English')
    work_type = fields.Selection([
        ('song', 'Song'),
        ('instrumental', 'Instrumental'),
        ('score', 'Film/TV Score'),
        ('jingle', 'Jingle/Commercial'),
        ('classical', 'Classical'),
        ('other', 'Other')
    ], string='Work Type', default='song', required=True)
    
    # Rights & Ownership
    composer_ids = fields.Many2many('res.partner', 'work_composer_rel', 'work_id', 'partner_id',
                                   string='Composers/Writers', 
                                   domain=[('is_writer', '=', True)])
    publisher_ids = fields.Many2many('res.partner', 'work_publisher_rel', 'work_id', 'partner_id',
                                    string='Publishers')
    
    # Splits & Shares
    split_ids = fields.One2many('publ.split', 'work_id', string='Splits')
    splits_total_writer = fields.Float(string='Total Writer Share (%)', 
                                      compute='_compute_splits_total', store=True)
    splits_total_publisher = fields.Float(string='Total Publisher Share (%)', 
                                         compute='_compute_splits_total', store=True)
    splits_validated = fields.Boolean(string='Splits Validated', 
                                     compute='_compute_splits_validated', store=True)
    
    # PRO Information
    registration_ids = fields.One2many('publ.registration', 'work_id', string='PRO Registrations')
    primary_pro = fields.Selection([
        ('ascap', 'ASCAP'),
        ('bmi', 'BMI'),
        ('sesac', 'SESAC'),
        ('socan', 'SOCAN'),
        ('prs', 'PRS for Music'),
        ('gema', 'GEMA'),
        ('sacem', 'SACEM'),
        ('other', 'Other')
    ], string='Primary PRO')
    
    # Recordings
    recording_ids = fields.One2many('music.recording', 'work_id', string='Recordings')
    recording_count = fields.Integer(string='Recordings Count', compute='_compute_recording_count')
    
    # Commercial
    sync_license_ids = fields.One2many('sync.license', 'work_id', string='Sync Licenses')
    commercial_status = fields.Selection([
        ('available', 'Available for Sync'),
        ('restricted', 'Restricted'),
        ('exclusive', 'Exclusive License'),
        ('not_available', 'Not Available')
    ], string='Commercial Status', default='available')
    
    # Notes & Attachments
    notes = fields.Html(string='Notes')
    lyric_document_ids = fields.Many2many('documents.document', 
                                         relation='work_lyric_doc_rel',
                                         string='Lyric Documents')
    demo_document_ids = fields.Many2many('documents.document',
                                        relation='work_demo_doc_rel', 
                                        string='Demo Recordings')
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('internal_work_id', _('New')) == _('New'):
            vals['internal_work_id'] = self.env['ir.sequence'].next_by_code('music.work') or _('New')
        return super().create(vals)

    @api.depends('duration_seconds')
    def _compute_duration_display(self):
        """Convert duration from seconds to MM:SS format"""
        for work in self:
            if work.duration_seconds:
                minutes = work.duration_seconds // 60
                seconds = work.duration_seconds % 60
                work.duration_display = f"{minutes}:{seconds:02d}"
            else:
                work.duration_display = False

    @api.depends('split_ids.writer_share', 'split_ids.publisher_share')
    def _compute_splits_total(self):
        """Calculate total writer and publisher shares"""
        for work in self:
            work.splits_total_writer = sum(work.split_ids.mapped('writer_share'))
            work.splits_total_publisher = sum(work.split_ids.mapped('publisher_share'))

    @api.depends('splits_total_writer', 'splits_total_publisher')
    def _compute_splits_validated(self):
        """Check if splits add up to 100%"""
        for work in self:
            # Allow small rounding errors
            writer_valid = abs(work.splits_total_writer - 100.0) < 0.01
            publisher_valid = abs(work.splits_total_publisher - 100.0) < 0.01
            work.splits_validated = writer_valid and publisher_valid

    @api.depends('recording_ids')
    def _compute_recording_count(self):
        for work in self:
            work.recording_count = len(work.recording_ids)

    @api.constrains('iswc')
    def _check_iswc_format(self):
        """Validate ISWC format"""
        for work in self:
            if work.iswc:
                # ISWC format: T-123456789-1 or T1234567890
                if not re.match(r'^T-?\d{9,10}-?\d?$', work.iswc.upper()):
                    raise ValidationError(_('Invalid ISWC format. Expected format: T-123456789-1'))

    @api.constrains('splits_total_writer', 'splits_total_publisher')
    def _check_splits_total(self):
        """Ensure splits don't exceed 100%"""
        for work in self:
            if work.splits_total_writer > 100.01:  # Allow small rounding
                raise ValidationError(_('Writer shares cannot exceed 100%'))
            if work.splits_total_publisher > 100.01:
                raise ValidationError(_('Publisher shares cannot exceed 100%'))

    def action_view_recordings(self):
        """Smart button to view related recordings"""
        return {
            'name': _('Recordings'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.recording',
            'view_mode': 'tree,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }

    def action_view_registrations(self):
        """View PRO registrations"""
        return {
            'name': _('PRO Registrations'),
            'type': 'ir.actions.act_window',
            'res_model': 'publ.registration',
            'view_mode': 'tree,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }

    def action_register_with_pro(self):
        """Wizard to register work with PRO"""
        return {
            'name': _('Register with PRO'),
            'type': 'ir.actions.act_window',
            'res_model': 'publ.registration.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_work_id': self.id},
        }

    def name_get(self):
        """Custom name display"""
        result = []
        for work in self:
            name = work.title
            if work.subtitle:
                name = f"{name} ({work.subtitle})"
            if work.iswc:
                name = f"{name} [{work.iswc}]"
            result.append((work.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced search including ISWC and alternate titles"""
        args = args or []
        if name:
            domain = [
                '|', '|', '|',
                ('title', operator, name),
                ('iswc', operator, name),
                ('internal_work_id', operator, name),
                ('alternate_titles', operator, name)
            ]
            return self.search(domain + args, limit=limit).name_get()
        return super().name_search(name, args, operator, limit)

    def copy(self, default=None):
        """Override copy to handle unique fields"""
        default = dict(default or {})
        default.update({
            'title': f"{self.title} (Copy)",
            'iswc': False,
            'internal_work_id': _('New'),
        })
        return super().copy(default)