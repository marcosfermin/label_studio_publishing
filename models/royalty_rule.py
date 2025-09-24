# -*- coding: utf-8 -*-

from odoo import models, fields, api


class RoyaltyRule(models.Model):
    _name = 'royalty.rule'
    _description = 'Royalty Rule'
    
    name = fields.Char(string='Rule Name', required=True)
    rule_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('flat_rate', 'Flat Rate')
    ], string='Rule Type')
    
    active = fields.Boolean(string='Active', default=True)
