# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MusicRights(models.Model):
    _name = 'music.rights'
    _description = 'Music Rights'
    _order = 'start_date desc'

    name = fields.Char(string='Rights Description', required=True)
    rights_type = fields.Selection([
        ('master', 'Master Recording Rights'),
        ('mechanical', 'Mechanical Rights'),
        ('performance', 'Performance Rights'),
        ('sync', 'Synchronization Rights'),
        ('print', 'Print Rights'),
        ('digital', 'Digital Rights')
    ], string='Rights Type', required=True)
    
    # Subject
    work_id = fields.Many2one('music.work', string='Work')
    recording_id = fields.Many2one('music.recording', string='Recording')
    release_id = fields.Many2one('music.release', string='Release')
    
    # Rights Holder
    owner_id = fields.Many2one('res.partner', string='Rights Owner', required=True)
    percentage = fields.Float(string='Ownership Percentage', default=100.0)
    
    # Territory & Term
    territory = fields.Text(string='Territory', default='Worldwide')
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date')
    perpetual = fields.Boolean(string='Perpetual', default=True)
    
    # Collection
    collection_society_id = fields.Many2one('res.partner', string='Collection Society',
                                           domain=[('is_pro', '=', True)])
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    verified = fields.Boolean(string='Verified', default=False)
    
    notes = fields.Text(string='Notes')

    @api.constrains('percentage')
    def _check_percentage(self):
        for rights in self:
            if not (0 <= rights.percentage <= 100):
                raise ValidationError(_('Ownership percentage must be between 0% and 100%'))

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rights in self:
            if rights.end_date and rights.start_date >= rights.end_date:
                raise ValidationError(_('End date must be after start date'))