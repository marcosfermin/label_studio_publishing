# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PublRegistration(models.Model):
    _name = 'publ.registration'
    _description = 'PRO (Performance Rights Organization) Registration'
    _order = 'id desc'
    
    # Basic Information
    name = fields.Char(string='Registration Name', required=True, 
                      help='Internal name for this registration')
    work_id = fields.Many2one('music.work', string='Musical Work', required=True, 
                             ondelete='cascade', index=True)
    
    # PRO Information
    pro_name = fields.Selection([
        ('ascap', 'ASCAP'),
        ('bmi', 'BMI'), 
        ('sesac', 'SESAC'),
        ('socan', 'SOCAN'),
        ('prs', 'PRS for Music'),
        ('gema', 'GEMA'),
        ('sacem', 'SACEM'),
        ('other', 'Other')
    ], string='PRO', required=True)
    
    # Registration Details
    registration_number = fields.Char(string='Registration Number', 
                                    help='PRO-assigned registration number')
    registration_date = fields.Date(string='Registration Date')
    registration_status = fields.Selection([
        ('pending', 'Pending'),
        ('registered', 'Registered'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn')
    ], string='Status', default='pending', required=True)
    
    # Active
    active = fields.Boolean(string='Active', default=True)
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            pro_display = dict(self._fields['pro_name'].selection).get(record.pro_name, record.pro_name)
            name = f"{record.work_id.title} - {pro_display}"
            if record.registration_number:
                name = f"{name} ({record.registration_number})"
            result.append((record.id, name))
        return result
