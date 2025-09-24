# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StudioPackage(models.Model):
    _name = 'studio.package'
    _description = 'Studio Service Package'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Package Name', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)

    description = fields.Text(string='Description')
    notes = fields.Text(string='Internal Notes')

    room_id = fields.Many2one(
        'studio.room',
        string='Suggested Room',
        help='Default studio room typically used for this package.',
        tracking=True,
    )
    duration_hours = fields.Float(
        string='Included Hours',
        default=4.0,
        help='Number of studio hours included in the package.',
    )
    engineer_included = fields.Boolean(
        string='Engineer Included',
        default=True,
        help='Whether an engineer is included in the package price.',
    )
    equipment_ids = fields.Many2many(
        'studio.equipment',
        string='Included Equipment',
        help='Equipment that is bundled with the package.',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    package_rate = fields.Monetary(
        string='Package Rate',
        required=True,
        tracking=True,
        help='Total price of the package including included services.',
    )

    additional_cost_notes = fields.Text(
        string='Additional Cost Notes',
        help='Describe any optional add-ons or exclusions for this package.',
    )

    @api.constrains('package_rate', 'duration_hours')
    def _check_positive_values(self):
        for package in self:
            if package.package_rate < 0:
                raise ValidationError(_('The package rate cannot be negative.'))
            if package.duration_hours <= 0:
                raise ValidationError(_('The included hours must be greater than zero.'))

