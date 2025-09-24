# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PublSplit(models.Model):
    _name = 'publ.split'
    _description = 'Publishing Split'
    _order = 'work_id, sequence, id'

    work_id = fields.Many2one('music.work', string='Work', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    contributor_id = fields.Many2one('res.partner', string='Contributor', required=True,
                                   domain=[('is_writer', '=', True)])
    role = fields.Selection([
        ('composer', 'Composer'),
        ('lyricist', 'Lyricist'),
        ('arranger', 'Arranger'),
        ('publisher', 'Publisher'),
        ('other', 'Other')
    ], string='Role', required=True)
    
    writer_share = fields.Float(string='Writer Share (%)', default=0.0)
    publisher_share = fields.Float(string='Publisher Share (%)', default=0.0)
    
    controlled = fields.Boolean(string='Controlled Composition', default=False,
                               help='True if controlled by the label for mechanical rates')
    admin_entity_id = fields.Many2one('res.partner', string='Admin Entity')
    
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    @api.constrains('writer_share', 'publisher_share')
    def _check_shares(self):
        for split in self:
            if split.writer_share < 0 or split.writer_share > 100:
                raise ValidationError(_('Writer share must be between 0% and 100%'))
            if split.publisher_share < 0 or split.publisher_share > 100:
                raise ValidationError(_('Publisher share must be between 0% and 100%'))

    def name_get(self):
        result = []
        for split in self:
            name = f"{split.contributor_id.name} - {split.role}"
            if split.writer_share > 0:
                name += f" (Writer: {split.writer_share}%)"
            if split.publisher_share > 0:
                name += f" (Publisher: {split.publisher_share}%)"
            result.append((split.id, name))
        return result