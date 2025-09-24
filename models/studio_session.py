# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class StudioSession(models.Model):
    _name = 'studio.session'
    _description = 'Studio Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc, id desc'

    name = fields.Char(string='Session Name', required=True, tracking=True, default='Session')
    booking_id = fields.Many2one('studio.booking', string='Booking', ondelete='set null', tracking=True)
    room_id = fields.Many2one('studio.room', string='Room', tracking=True)
    engineer_id = fields.Many2one('res.partner', string='Engineer', domain=[('is_engineer', '=', True)])
    client_id = fields.Many2one('res.partner', string='Client', tracking=True)
    artist_id = fields.Many2one('res.partner', string='Primary Artist', domain=[('is_artist', '=', True)])
    project_name = fields.Char(string='Project Name')
    start_time = fields.Datetime(string='Start Time', tracking=True)
    end_time = fields.Datetime(string='End Time', tracking=True)
    duration_hours = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    notes = fields.Html(string='Session Notes')
    deliverable_links = fields.Text(string='Deliverable Links')
    rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor')
    ], string='Client Feedback')
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='scheduled', tracking=True)
    active = fields.Boolean(string='Active', default=True)

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for session in self:
            if session.start_time and session.end_time and session.end_time >= session.start_time:
                delta = session.end_time - session.start_time
                session.duration_hours = delta.total_seconds() / 3600.0
            else:
                session.duration_hours = 0.0

    def action_start_session(self):
        for session in self:
            if not session.start_time:
                session.start_time = fields.Datetime.now()
            session.state = 'in_progress'

    def action_complete_session(self):
        for session in self:
            if not session.end_time:
                session.end_time = fields.Datetime.now()
            session.state = 'completed'

    def action_cancel_session(self):
        self.write({'state': 'cancelled'})
