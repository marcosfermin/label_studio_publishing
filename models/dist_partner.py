# -*- coding: utf-8 -*-

from odoo import models, fields, api


class DistPartner(models.Model):
    _name = 'dist.partner'
    _description = 'Distribution Partner'
    
    name = fields.Char(string='Partner Name', required=True)
    partner_type = fields.Selection([
        ('digital', 'Digital Platform'),
        ('physical', 'Physical Distribution'),
        ('streaming', 'Streaming Platform')
    ], string='Partner Type')
    partner_id = fields.Many2one('res.partner', string='Contact')
    
    active = fields.Boolean(string='Active', default=True)
