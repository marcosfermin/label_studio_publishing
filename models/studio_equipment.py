# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StudioEquipment(models.Model):
    _name = 'studio.equipment'
    _description = 'Studio Equipment'
    
    name = fields.Char(string='Equipment Name', required=True)
    equipment_type = fields.Selection([
        ('microphone', 'Microphone'),
        ('instrument', 'Instrument'),
        ('amplifier', 'Amplifier'),
        ('mixer', 'Mixer'),
        ('other', 'Other')
    ], string='Type')
    
    active = fields.Boolean(string='Active', default=True)
