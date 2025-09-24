# -*- coding: utf-8 -*-

from odoo import models, fields, api


class RoyaltyStatement(models.Model):
    _name = 'royalty.statement'
    _description = 'Royalty Statement'
    
    name = fields.Char(string='Statement Name', required=True)
    statement_date = fields.Date(string='Statement Date')
    partner_id = fields.Many2one('res.partner', string='Partner')
    
    active = fields.Boolean(string='Active', default=True)
