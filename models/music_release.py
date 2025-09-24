# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class MusicRelease(models.Model):
    _name = 'music.release'
    _description = 'Music Release'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'release_date desc, title'

    # Basic Information
    title = fields.Char(string='Release Title', required=True, tracking=True, index=True)
    release_type = fields.Selection([
        ('single', 'Single'),
        ('ep', 'EP'),
        ('album', 'Album'),
        ('compilation', 'Compilation'),
        ('soundtrack', 'Soundtrack'),
        ('remix_album', 'Remix Album'),
        ('live_album', 'Live Album')
    ], string='Release Type', required=True, default='single', tracking=True)
    
    # Identification
    catalog_number = fields.Char(string='Catalog Number', required=True, copy=False,
                                default=lambda self: _('New'))
    upc = fields.Char(string='UPC/EAN', help='Universal Product Code / European Article Number',
                     index=True)
    grid = fields.Char(string='GRid', help='Global Release Identifier')
    
    # Release Details
    release_date = fields.Date(string='Release Date', required=True, tracking=True)
    original_release_date = fields.Date(string='Original Release Date',
                                       help='For reissues, date of original release')
    
    # Artists
    main_artist_ids = fields.Many2many('res.partner', 'release_main_artist_rel',
                                      'release_id', 'partner_id',
                                      string='Main Artist(s)',
                                      domain=[('is_artist', '=', True)])
    various_artists = fields.Boolean(string='Various Artists', default=False)
    
    # Label & Distribution
    label_id = fields.Many2one('res.partner', string='Record Label',
                              domain=[('is_company', '=', True)])
    distributor_id = fields.Many2one('res.partner', string='Distributor',
                                    domain=[('is_distributor', '=', True)])
    
    # Tracklist
    recording_ids = fields.Many2many('music.recording', 'release_recording_rel',
                                    'release_id', 'recording_id',
                                    string='Recordings')
    track_count = fields.Integer(string='Track Count', compute='_compute_track_count', store=True)
    total_duration = fields.Integer(string='Total Duration (seconds)', 
                                   compute='_compute_total_duration', store=True)
    total_duration_display = fields.Char(string='Total Duration', 
                                        compute='_compute_total_duration_display', store=True)
    
    # Artwork & Media
    cover_artwork = fields.Binary(string='Cover Artwork', attachment=True)
    cover_artwork_name = fields.Char(string='Cover Artwork File Name')
    back_artwork = fields.Binary(string='Back Artwork', attachment=True)
    booklet_artwork = fields.Binary(string='Booklet Artwork', attachment=True)
    
    # Metadata Package
    metadata_complete = fields.Boolean(string='Metadata Complete', default=False)
    ddex_ready = fields.Boolean(string='DDEX Ready', compute='_compute_ddex_ready', store=True)
    
    # Territories & Pricing
    territory = fields.Text(string='Release Territories', default='Worldwide')
    price_tier = fields.Selection([
        ('budget', 'Budget'),
        ('mid_price', 'Mid Price'),
        ('full_price', 'Full Price'),
        ('premium', 'Premium')
    ], string='Price Tier', default='full_price')
    
    # Commercial Information
    genre_ids = fields.Many2many('music.genre', string='Genres')
    language = fields.Char(string='Primary Language', default='English')
    parental_advisory = fields.Boolean(string='Parental Advisory (Explicit)', default=False)
    
    # Rights & Licensing
    p_line = fields.Char(string='P-Line', help='Phonogram copyright notice')
    c_line = fields.Char(string='C-Line', help='Composition copyright notice')
    mechanical_license_required = fields.Boolean(string='Mechanical License Required', default=False)
    
    # Commercial Performance
    total_streams = fields.Integer(string='Total Streams', readonly=True)
    total_downloads = fields.Integer(string='Total Downloads', readonly=True)
    total_physical_sales = fields.Integer(string='Total Physical Sales', readonly=True)
    peak_chart_position = fields.Integer(string='Peak Chart Position')
    
    # Status & Workflow
    status = fields.Selection([
        ('draft', 'Draft'),
        ('metadata_review', 'Metadata Review'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered to Distributors'),
        ('released', 'Released'),
        ('archived', 'Archived')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Related Records
    deal_ids = fields.Many2many('label.deal', string='Related Deals',
                               compute='_compute_deal_ids', store=True)
    
    # Documents
    liner_notes = fields.Html(string='Liner Notes')
    contract_document_ids = fields.Many2many('documents.document',
                                           relation='release_contract_doc_rel',
                                           string='Contract Documents')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.model
    def create(self, vals):
        if vals.get('catalog_number', _('New')) == _('New'):
            vals['catalog_number'] = self.env['ir.sequence'].next_by_code('music.release') or _('New')
        return super().create(vals)

    @api.depends('recording_ids')
    def _compute_track_count(self):
        for release in self:
            release.track_count = len(release.recording_ids)

    @api.depends('recording_ids.duration_seconds')
    def _compute_total_duration(self):
        for release in self:
            release.total_duration = sum(release.recording_ids.mapped('duration_seconds') or [0])

    @api.depends('total_duration')
    def _compute_total_duration_display(self):
        for release in self:
            if release.total_duration:
                hours = release.total_duration // 3600
                minutes = (release.total_duration % 3600) // 60
                seconds = release.total_duration % 60
                if hours > 0:
                    release.total_duration_display = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    release.total_duration_display = f"{minutes}:{seconds:02d}"
            else:
                release.total_duration_display = False

    @api.depends('main_artist_ids')
    def _compute_deal_ids(self):
        """Find related deals based on main artists"""
        for release in self:
            if release.main_artist_ids:
                deals = self.env['label.deal'].search([
                    ('party_id', 'in', release.main_artist_ids.ids),
                    ('status', 'in', ['signed', 'active'])
                ])
                release.deal_ids = [(6, 0, deals.ids)]
            else:
                release.deal_ids = [(5, 0, 0)]

    @api.depends('metadata_complete', 'cover_artwork', 'recording_ids')
    def _compute_ddex_ready(self):
        """Check if release is ready for DDEX delivery"""
        for release in self:
            ready = (
                release.metadata_complete and
                release.cover_artwork and
                release.recording_ids and
                all(recording.isrc for recording in release.recording_ids)
            )
            release.ddex_ready = ready

    @api.constrains('upc')
    def _check_upc_format(self):
        """Validate UPC/EAN format"""
        for release in self:
            if release.upc:
                # Remove spaces and hyphens
                upc_clean = release.upc.replace('-', '').replace(' ', '')
                # UPC should be 12 digits, EAN should be 13
                if not re.match(r'^\d{12,13}$', upc_clean):
                    raise ValidationError(_('UPC/EAN must be 12 or 13 digits'))
                release.upc = upc_clean

    @api.constrains('release_date', 'original_release_date')
    def _check_release_dates(self):
        """Validate release dates"""
        for release in self:
            if (release.original_release_date and release.release_date and 
                release.original_release_date > release.release_date):
                raise ValidationError(_('Original release date cannot be after current release date'))

    def action_view_recordings(self):
        """Smart button to view recordings"""
        return {
            'name': _('Recordings'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.recording',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.recording_ids.ids)],
        }

    def action_view_deals(self):
        """Smart button to view related deals"""
        return {
            'name': _('Related Deals'),
            'type': 'ir.actions.act_window',
            'res_model': 'label.deal',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.deal_ids.ids)],
        }

    def action_generate_ddex_package(self):
        """Generate DDEX ERN package"""
        if not self.ddex_ready:
            raise ValidationError(_('Release is not ready for DDEX delivery. Please complete metadata and ensure all recordings have ISRCs.'))
        
        return {
            'name': _('Generate DDEX Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'ddex.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_release_id': self.id},
        }

    def action_approve_release(self):
        """Approve release for distribution"""
        if not self.ddex_ready:
            raise ValidationError(_('Release cannot be approved without complete metadata'))
        
        self.status = 'approved'
        self.message_post(body=_('Release approved for distribution'))

    def action_mark_delivered(self):
        """Mark as delivered to distributors"""
        self.status = 'delivered'
        self.message_post(body=_('Release delivered to distributors'))

    def action_release(self):
        """Mark as released"""
        self.status = 'released'
        self.message_post(body=_('Release is now live'))
        
        # Update recordings status
        self.recording_ids.write({'status': 'released'})

    def name_get(self):
        """Custom name display"""
        result = []
        for release in self:
            name = release.title
            if release.main_artist_ids and not release.various_artists:
                artists = ', '.join(release.main_artist_ids.mapped('name')[:2])
                if len(release.main_artist_ids) > 2:
                    artists += f" +{len(release.main_artist_ids) - 2} more"
                name = f"{artists} - {name}"
            if release.catalog_number:
                name = f"{name} [{release.catalog_number}]"
            result.append((release.id, name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced search including catalog number and artist names"""
        args = args or []
        if name:
            domain = [
                '|', '|', '|',
                ('title', operator, name),
                ('catalog_number', operator, name),
                ('upc', operator, name),
                ('main_artist_ids.name', operator, name)
            ]
            return self.search(domain + args, limit=limit).name_get()
        return super().name_search(name, args, operator, limit)

    def copy(self, default=None):
        """Override copy to handle unique fields"""
        default = dict(default or {})
        default.update({
            'title': f"{self.title} (Copy)",
            'catalog_number': _('New'),
            'upc': False,
            'status': 'draft',
        })
        return super().copy(default)

