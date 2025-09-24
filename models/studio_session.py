# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StudioSession(models.Model):
    _name = 'studio.session'
    _description = 'Studio Session'
    
    name = fields.Char(string='Session Name', required=True)
    session_date = fields.Date(string='Session Date')
    artist_id = fields.Many2one('res.partner', string='Artist')
    
    active = fields.Boolean(string='Active', default=True)
