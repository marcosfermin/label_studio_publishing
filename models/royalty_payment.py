# -*- coding: utf-8 -*-

from odoo import models, fields, api


class RoyaltyPayment(models.Model):
    _name = 'royalty.payment'
    _description = 'Royalty Payment'
    
    name = fields.Char(string='Payment Name', required=True)
    payment_date = fields.Date(string='Payment Date')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency')
    partner_id = fields.Many2one('res.partner', string='Partner')
    
    active = fields.Boolean(string='Active', default=True)
