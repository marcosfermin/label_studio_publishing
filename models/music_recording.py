# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class MusicRecording(models.Model):
    _name = 'music.recording'
    _description = 'Master Recording'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'title'

    # Basic Information
    title = fields.Char(string='Track Title', required=True, tracking=True, index=True)
    version = fields.Char(string='Version', help='e.g., Radio Edit, Extended, Live, Acoustic')
    
    # Identification
    isrc = fields.Char(string='ISRC', help='International Standard Recording Code',
                       index=True)
    internal_recording_id = fields.Char(string='Internal Recording ID', required=True, copy=False,
                                       default=lambda self: _('New'))
    
    # Associated Work
    work_id = fields.Many2one('music.work', string='Associated Work', index=True)
    
    # Artists & Contributors
    main_artist_ids = fields.Many2many('res.partner', 'recording_main_artist_rel', 
                                      'recording_id', 'partner_id',
                                      string='Main Artist(s)',
                                      domain=[('is_artist', '=', True)])
    featured_artist_ids = fields.Many2many('res.partner', 'recording_featured_artist_rel',
                                          'recording_id', 'partner_id', 
                                          string='Featured Artist(s)',
                                          domain=[('is_artist', '=', True)])
    producer_ids = fields.Many2many('res.partner', 'recording_producer_rel',
                                   'recording_id', 'partner_id',
                                   string='Producer(s)',
                                   domain=[('is_producer', '=', True)])
    
    # Recording Details
    recording_date = fields.Date(string='Recording Date')
    bpm = fields.Integer(string='BPM (Tempo)')
    key_signature = fields.Selection([
        ('c_major', 'C Major'), ('c_minor', 'C Minor'),
        ('c_sharp_major', 'C# Major'), ('c_sharp_minor', 'C# Minor'),
        ('d_major', 'D Major'), ('d_minor', 'D Minor'),
        ('d_sharp_major', 'D# Major'), ('d_sharp_minor', 'D# Minor'),
        ('e_major', 'E Major'), ('e_minor', 'E Minor'),
        ('f_major', 'F Major'), ('f_minor', 'F Minor'),
        ('f_sharp_major', 'F# Major'), ('f_sharp_minor', 'F# Minor'),
        ('g_major', 'G Major'), ('g_minor', 'G Minor'),
        ('g_sharp_major', 'G# Major'), ('g_sharp_minor', 'G# Minor'),
        ('a_major', 'A Major'), ('a_minor', 'A Minor'),
        ('a_sharp_major', 'A# Major'), ('a_sharp_minor', 'A# Minor'),
        ('b_major', 'B Major'), ('b_minor', 'B Minor'),
    ], string='Key Signature')
    
    duration_seconds = fields.Integer(string='Duration (seconds)')
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display', store=True)
    
    # Technical Specs
    sample_rate = fields.Selection([
        ('44100', '44.1 kHz'),
        ('48000', '48 kHz'),
        ('88200', '88.2 kHz'),
        ('96000', '96 kHz'),
        ('192000', '192 kHz')
    ], string='Sample Rate', default='44100')
    bit_depth = fields.Selection([
        ('16', '16-bit'),
        ('24', '24-bit'),
        ('32', '32-bit')
    ], string='Bit Depth', default='24')
    
    # Audio Characteristics
    loudness_lufs = fields.Float(string='Loudness (LUFS)', help='Integrated loudness measurement')
    peak_dbfs = fields.Float(string='Peak Level (dBFS)', help='True peak level')
    parental_advisory = fields.Boolean(string='Parental Advisory (Explicit)', default=False)
    
    # Ownership & Rights
    p_line = fields.Char(string='P-Line', help='Phonogram copyright notice')
    ownership_percentage = fields.Float(string='Label Ownership %', default=100.0,
                                       help='Percentage owned by the label')
    
    # Studio Session Link
    studio_session_ids = fields.Many2many('studio.session', string='Studio Sessions')
    
    # Classification
    genre_ids = fields.Many2many('music.genre', string='Genres')
    language = fields.Char(string='Language', default='English')
    
    # Media Files
    master_file = fields.Binary(string='Master Audio File', attachment=True)
    master_file_name = fields.Char(string='Master File Name')
    artwork = fields.Binary(string='Artwork', attachment=True)
    artwork_name = fields.Char(string='Artwork File Name')
    
    # Related Documents
    session_document_ids = fields.Many2many('documents.document',
                                           relation='recording_session_doc_rel',
                                           string='Session Documents')
    
    # Release Information
    release_ids = fields.Many2many('music.release', 'release_recording_rel',
                                  'recording_id', 'release_id', 
                                  string='Releases')
    first_release_date = fields.Date(string='First Release Date', compute='_compute_first_release_date', store=True)
    
    # Commercial Performance
    total_streams = fields.Integer(string='Total Streams', readonly=True)
    total_downloads = fields.Integer(string='Total Downloads', readonly=True)
    total_physical_sales = fields.Integer(string='Total Physical Sales', readonly=True)
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('mastered', 'Mastered'),
        ('approved', 'Approved'),
        ('released', 'Released'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('internal_recording_id', _('New')) == _('New'):
            vals['internal_recording_id'] = self.env['ir.sequence'].next_by_code('music.recording') or _('New')
        return super().create(vals)

    @api.depends('duration_seconds')
    def _compute_duration_display(self):
        """Convert duration from seconds to MM:SS format"""
        for recording in self:
            if recording.duration_seconds:
                minutes = recording.duration_seconds // 60
                seconds = recording.duration_seconds % 60
                recording.duration_display = f"{minutes}:{seconds:02d}"
            else:
                recording.duration_display = False

    @api.depends('release_ids.release_date')
    def _compute_first_release_date(self):
        """Find earliest release date"""
        for recording in self:
            release_dates = recording.release_ids.mapped('release_date')
            if release_dates:
                recording.first_release_date = min(release_dates)
            else:
                recording.first_release_date = False

    @api.constrains('isrc')
    def _check_isrc_format(self):
        """Validate ISRC format"""
        for recording in self:
            if recording.isrc:
                # ISRC format: CC-XXX-YY-NNNNN
                isrc_clean = recording.isrc.replace('-', '').replace(' ', '').upper()
                if not re.match(r'^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$', isrc_clean):
                    raise ValidationError(_('Invalid ISRC format. Expected format: CC-XXX-YY-NNNNN'))
                
                # Reformat to standard format
                formatted_isrc = f"{isrc_clean[:2]}-{isrc_clean[2:5]}-{isrc_clean[5:7]}-{isrc_clean[7:]}"
                recording.isrc = formatted_isrc

    @api.constrains('ownership_percentage')
    def _check_ownership_percentage(self):
        """Validate ownership percentage"""
        for recording in self:
            if not (0 <= recording.ownership_percentage <= 100):
                raise ValidationError(_('Ownership percentage must be between 0% and 100%'))

    @api.constrains('duration_seconds')
    def _check_duration(self):
        """Validate duration is reasonable"""
        for recording in self:
            if recording.duration_seconds and recording.duration_seconds < 0:
                raise ValidationError(_('Duration cannot be negative'))
            if recording.duration_seconds and recording.duration_seconds > 7200:  # 2 hours
                raise ValidationError(_('Duration seems unreasonably long (>2 hours). Please verify.'))

    def action_view_releases(self):
        """Smart button to view related releases"""
        return {
            'name': _('Releases'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.release',
            'view_mode': 'tree,form',
            'domain': [('recording_ids', 'in', self.id)],
        }

    def action_view_royalty_statements(self):
        """View royalty statements for this recording"""
        return {
            'name': _('Royalty Statements'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.usage.line',
            'view_mode': 'tree,form',
            'domain': [('recording_id', '=', self.id)],
        }

    def action_view_studio_sessions(self):
        """View related studio sessions"""
        return {
            'name': _('Studio Sessions'),
            'type': 'ir.actions.act_window',
            'res_model': 'studio.session',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.studio_session_ids.ids)],
        }

    def name_get(self):
        """Custom name display"""
        result = []
        for recording in self:
            name = recording.title
            if recording.version:
                name = f"{name} ({recording.version})"
            # Add main artists
            if recording.main_artist_ids:
                artists = ', '.join(recording.main_artist_ids.mapped('name')[:2])
                if len(recording.main_artist_ids) > 2:
                    artists += f" +{len(recording.main_artist_ids) - 2} more"
                name = f"{artists} - {name}"
            if recording.isrc:
                name = f"{name} [{recording.isrc}]"
            result.append((recording.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced search including ISRC and artist names"""
        args = args or []
        if name:
            domain = [
                '|', '|', '|', '|',
                ('title', operator, name),
                ('isrc', operator, name),
                ('internal_recording_id', operator, name),
                ('main_artist_ids.name', operator, name),
                ('featured_artist_ids.name', operator, name)
            ]
            return self.search(domain + args, limit=limit).name_get()
        return super().name_search(name, args, operator, limit)

    def copy(self, default=None):
        """Override copy to handle unique fields"""
        default = dict(default or {})
        default.update({
            'title': f"{self.title} (Copy)",
            'isrc': False,
            'internal_recording_id': _('New'),
        })
        return super().copy(default)

    def action_generate_isrc(self):
        """Generate ISRC if not set"""
        if not self.isrc:
            # This would integrate with an ISRC agency or generate based on label prefix
            # For now, create a placeholder
            country_code = self.env.company.country_id.code or 'US'
            registrant_code = 'ABC'  # This should come from configuration
            year_code = str(fields.Date.today().year)[-2:]
            
            # Get next sequence number for this year
            existing_count = self.search_count([
                ('isrc', 'like', f'{country_code}-{registrant_code}-{year_code}-%')
            ])
            designation = f"{existing_count + 1:05d}"
            
            self.isrc = f"{country_code}-{registrant_code}-{year_code}-{designation}"
            
            self.message_post(body=f"ISRC generated: {self.isrc}")

    def action_update_sales_data(self):
        """Update sales data from royalty statements"""
        usage_lines = self.env['royalty.usage.line'].search([
            ('recording_id', '=', self.id)
        ])
        
        # Aggregate by usage type
        streams = sum(usage_lines.filtered(lambda l: l.usage_type == 'stream').mapped('units'))
        downloads = sum(usage_lines.filtered(lambda l: l.usage_type == 'download').mapped('units'))
        physical = sum(usage_lines.filtered(lambda l: l.usage_type == 'physical').mapped('units'))
        
        self.write({
            'total_streams': streams,
            'total_downloads': downloads,
            'total_physical_sales': physical,
        })