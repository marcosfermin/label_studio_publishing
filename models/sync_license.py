# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SyncLicense(models.Model):
    _name = 'sync.license'
    _description = 'Synchronization License'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'license_date desc'
    
    # Basic Information
    name = fields.Char(string='License Name', required=True, 
                      help='Internal name for this sync license')
    work_id = fields.Many2one('music.work', string='Musical Work', required=True, 
                             ondelete='cascade', index=True)
    
    # License Details
    license_number = fields.Char(string='License Number', 
                                help='Internal license reference number')
    license_date = fields.Date(string='License Date', default=fields.Date.today)
    license_type = fields.Selection([
        ('film', 'Film/Movie'),
        ('tv', 'Television'),
        ('commercial', 'Commercial/Advertisement'),
        ('video_game', 'Video Game'),
        ('streaming', 'Streaming Platform'),
        ('web', 'Web/Online Content'),
        ('other', 'Other')
    ], string='License Type', required=True)
    
    # Licensee Information
    licensee_id = fields.Many2one('res.partner', string='Licensee', required=True,
                                 help='Company or individual licensing the music')
    project_name = fields.Char(string='Project Name', 
                              help='Name of the film, show, commercial, etc.')
    project_description = fields.Text(string='Project Description')
    
    # Usage Details
    usage_type = fields.Selection([
        ('background', 'Background Music'),
        ('theme', 'Theme Song'),
        ('promotional', 'Promotional'),
        ('trailer', 'Trailer'),
        ('opening', 'Opening Credits'),
        ('closing', 'Closing Credits'),
        ('featured', 'Featured Performance'),
        ('other', 'Other')
    ], string='Usage Type', default='background')
    
    duration_licensed = fields.Float(string='Duration Licensed (seconds)',
                                    help='How many seconds of the track are licensed')
    territory = fields.Selection([
        ('worldwide', 'Worldwide'),
        ('us', 'United States'),
        ('canada', 'Canada'),
        ('europe', 'Europe'),
        ('uk', 'United Kingdom'),
        ('other', 'Other')
    ], string='Territory', default='us', required=True)
    
    territory_other = fields.Char(string='Other Territory',
                                 help='Specify territory if "Other" is selected')
    
    # Financial Terms
    license_fee = fields.Monetary(string='License Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 default=lambda self: self.env.company.currency_id)
    
    # Dates & Terms
    start_date = fields.Date(string='License Start Date')
    end_date = fields.Date(string='License End Date')
    is_perpetual = fields.Boolean(string='Perpetual License', default=False)
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Additional Information
    notes = fields.Html(string='Notes')
    restrictions = fields.Text(string='Restrictions & Conditions')
    
    # Computed Fields
    work_title = fields.Char(related='work_id.title', string='Work Title', store=True)
    work_iswc = fields.Char(related='work_id.iswc', string='ISWC', store=True)
    
    # Active
    active = fields.Boolean(string='Active', default=True)
    
    @api.constrains('territory', 'territory_other')
    def _check_territory_other(self):
        """Ensure territory_other is filled when territory is 'other'"""
        for record in self:
            if record.territory == 'other' and not record.territory_other:
                raise ValidationError(_('Please specify the territory when "Other" is selected.'))
    
    @api.constrains('start_date', 'end_date')
    def _check_license_dates(self):
        """Ensure end date is after start date"""
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(_('License end date must be after the start date.'))
    
    @api.onchange('territory')
    def _onchange_territory(self):
        """Clear territory_other when territory is not 'other'"""
        if self.territory != 'other':
            self.territory_other = False
    
    @api.onchange('is_perpetual')
    def _onchange_is_perpetual(self):
        """Clear end_date when perpetual license is selected"""
        if self.is_perpetual:
            self.end_date = False
    
    @api.onchange('status')
    def _onchange_status(self):
        """Set start_date when status changes to active"""
        if self.status == 'active' and not self.start_date:
            self.start_date = fields.Date.today()
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.work_id.title}"
            if record.project_name:
                name = f"{name} - {record.project_name}"
            if record.license_number:
                name = f"{name} ({record.license_number})"
            result.append((record.id, name))
        return result
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced search including work title and project name"""
        args = args or []
        if name:
            domain = [
                '|', '|', '|',
                ('name', operator, name),
                ('work_title', operator, name),
                ('project_name', operator, name),
                ('license_number', operator, name)
            ]
            return self.search(domain + args, limit=limit).name_get()
        return super().name_search(name, args, operator, limit)
    
    def action_activate(self):
        """Activate the license"""
        self.write({
            'status': 'active',
            'start_date': self.start_date or fields.Date.today()
        })
    
    def action_cancel(self):
        """Cancel the license"""
        self.write({'status': 'cancelled'})
    
    def action_renew(self):
        """Create a renewal wizard or duplicate license"""
        return {
            'name': _('Renew Sync License'),
            'type': 'ir.actions.act_window',
            'res_model': 'sync.license',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_work_id': self.work_id.id,
                'default_licensee_id': self.licensee_id.id,
                'default_project_name': f"{self.project_name} (Renewal)",
                'default_license_type': self.license_type,
                'default_territory': self.territory,
                'default_license_fee': self.license_fee,
            },
        }
