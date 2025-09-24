# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudioRoom(models.Model):
    _name = 'studio.room'
    _description = 'Recording Studio Room'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Room Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Location & Physical
    location = fields.Char(string='Location/Building')
    capacity = fields.Integer(string='Capacity (people)', default=6)
    size_sqft = fields.Float(string='Size (sq ft)')
    
    # Pricing
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    hourly_rate = fields.Monetary(string='Hourly Rate', currency_field='currency_id')
    day_rate = fields.Monetary(string='Day Rate (8+ hours)', currency_field='currency_id')
    overtime_rate = fields.Monetary(string='Overtime Rate (per hour)', currency_field='currency_id')
    
    # Calendar Integration
    resource_id = fields.Many2one('resource.resource', string='Calendar Resource', 
                                 ondelete='cascade')
    calendar_id = fields.Many2one('resource.calendar', string='Working Hours',
                                 related='resource_id.calendar_id', readonly=True)
    color = fields.Integer(string='Calendar Color', default=1)
    
    # Features & Equipment
    facilities = fields.Text(string='Room Facilities', 
                           help='ISO booth, piano, amp collection, etc.')
    equipment_ids = fields.Many2many('studio.equipment', string='Included Equipment')
    console_type = fields.Char(string='Mixing Console')
    monitors = fields.Char(string='Studio Monitors')
    
    # Technical Specs
    acoustic_treatment = fields.Selection([
        ('basic', 'Basic Treatment'),
        ('professional', 'Professional Treatment'),
        ('world_class', 'World Class Acoustics')
    ], string='Acoustic Treatment')
    
    isolation_booths = fields.Integer(string='Number of ISO Booths', default=0)
    has_piano = fields.Boolean(string='Has Piano', default=False)
    has_drums = fields.Boolean(string='Has Drum Kit', default=False)
    has_amps = fields.Boolean(string='Has Guitar/Bass Amps', default=False)
    
    # Availability
    active = fields.Boolean(string='Active', default=True, tracking=True)
    maintenance_mode = fields.Boolean(string='Under Maintenance', default=False, tracking=True)
    availability_notes = fields.Text(string='Availability Notes')
    
    # Statistics
    booking_count = fields.Integer(string='Total Bookings', compute='_compute_booking_stats')
    utilization_rate = fields.Float(string='Utilization Rate (%)', compute='_compute_utilization_rate')
    total_revenue = fields.Monetary(string='Total Revenue', compute='_compute_booking_stats',
                                   currency_field='currency_id')
    
    # Current Status
    current_booking_id = fields.Many2one('studio.booking', string='Current Booking',
                                        compute='_compute_current_booking')
    is_occupied = fields.Boolean(string='Currently Occupied', compute='_compute_current_booking')
    next_booking_id = fields.Many2one('studio.booking', string='Next Booking',
                                     compute='_compute_next_booking')

    @api.model
    def create(self, vals):
        """Create resource when creating room"""
        if not vals.get('resource_id'):
            resource_vals = {
                'name': vals.get('name', 'Studio Room'),
                'resource_type': 'material',
                'user_id': False,
            }
            resource = self.env['resource.resource'].create(resource_vals)
            vals['resource_id'] = resource.id
        return super().create(vals)

    def write(self, vals):
        """Sync name changes to resource"""
        result = super().write(vals)
        if 'name' in vals and self.resource_id:
            self.resource_id.name = vals['name']
        return result

    @api.depends()
    def _compute_booking_stats(self):
        for room in self:
            bookings = self.env['studio.booking'].search([
                ('room_id', '=', room.id),
                ('status', 'in', ['confirmed', 'in_session', 'completed'])
            ])
            room.booking_count = len(bookings)
            room.total_revenue = sum(bookings.mapped('total_amount'))

    @api.depends()
    def _compute_utilization_rate(self):
        """Calculate utilization rate for last 30 days"""
        for room in self:
            # Simplified calculation - in production, use proper date ranges
            total_hours = 30 * 8  # 30 days * 8 hours per day
            booked_hours = 0
            
            # Get bookings from last 30 days
            from datetime import datetime, timedelta
            last_30_days = datetime.now() - timedelta(days=30)
            
            bookings = self.env['studio.booking'].search([
                ('room_id', '=', room.id),
                ('start_datetime', '>=', last_30_days),
                ('status', 'in', ['confirmed', 'in_session', 'completed'])
            ])
            
            for booking in bookings:
                if booking.start_datetime and booking.end_datetime:
                    duration = booking.end_datetime - booking.start_datetime
                    booked_hours += duration.total_seconds() / 3600
            
            room.utilization_rate = (booked_hours / total_hours * 100) if total_hours > 0 else 0

    @api.depends()
    def _compute_current_booking(self):
        """Find current active booking"""
        for room in self:
            current_booking = self.env['studio.booking'].search([
                ('room_id', '=', room.id),
                ('status', '=', 'in_session'),
                ('start_datetime', '<=', fields.Datetime.now()),
                ('end_datetime', '>=', fields.Datetime.now())
            ], limit=1)
            
            room.current_booking_id = current_booking.id if current_booking else False
            room.is_occupied = bool(current_booking)

    @api.depends()
    def _compute_next_booking(self):
        """Find next upcoming booking"""
        for room in self:
            next_booking = self.env['studio.booking'].search([
                ('room_id', '=', room.id),
                ('status', 'in', ['confirmed', 'pending']),
                ('start_datetime', '>', fields.Datetime.now())
            ], order='start_datetime asc', limit=1)
            
            room.next_booking_id = next_booking.id if next_booking else False

    def action_view_bookings(self):
        """View all bookings for this room"""
        return {
            'name': _('Room Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'studio.booking',
            'view_mode': 'calendar,tree,form',
            'domain': [('room_id', '=', self.id)],
            'context': {
                'default_room_id': self.id,
                'search_default_upcoming': 1
            }
        }

    def action_view_current_booking(self):
        """View current booking"""
        if self.current_booking_id:
            return {
                'name': _('Current Booking'),
                'type': 'ir.actions.act_window',
                'res_model': 'studio.booking',
                'res_id': self.current_booking_id.id,
                'view_mode': 'form',
            }

    def action_book_room(self):
        """Quick booking action"""
        return {
            'name': _('Book Room'),
            'type': 'ir.actions.act_window',
            'res_model': 'studio.booking',
            'view_mode': 'form',
            'context': {
                'default_room_id': self.id,
                'default_start_datetime': fields.Datetime.now(),
            },
            'target': 'new'
        }

    def check_availability(self, start_datetime, end_datetime):
        """Check if room is available for given time slot"""
        self.ensure_one()
        
        conflicting_bookings = self.env['studio.booking'].search([
            ('room_id', '=', self.id),
            ('status', 'in', ['confirmed', 'in_session']),
            '|',
            '&', ('start_datetime', '<=', start_datetime), ('end_datetime', '>', start_datetime),
            '&', ('start_datetime', '<', end_datetime), ('end_datetime', '>=', end_datetime),
        ])
        
        return len(conflicting_bookings) == 0

    @api.constrains('hourly_rate', 'day_rate')
    def _check_rates(self):
        for room in self:
            if room.hourly_rate < 0 or room.day_rate < 0:
                raise ValidationError(_('Rates cannot be negative'))