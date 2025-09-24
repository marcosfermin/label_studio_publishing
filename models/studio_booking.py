# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class StudioBooking(models.Model):
    _name = 'studio.booking'
    _description = 'Studio Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    name = fields.Char(string='Booking Reference', required=True, copy=False,
                      default=lambda self: _('New'))
    
    # Client & Contact
    client_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    contact_name = fields.Char(string='Contact Name')
    contact_phone = fields.Char(string='Contact Phone')
    contact_email = fields.Char(string='Contact Email')
    
    # Booking Details
    room_id = fields.Many2one('studio.room', string='Room', required=True, tracking=True)
    engineer_id = fields.Many2one('res.partner', string='Engineer',
                                 domain=[('is_engineer', '=', True)])
    
    # Date & Time
    start_datetime = fields.Datetime(string='Start Date & Time', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End Date & Time', required=True, tracking=True)
    duration_hours = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    
    # Services
    service_type = fields.Selection([
        ('recording', 'Recording'),
        ('mixing', 'Mixing'),
        ('mastering', 'Mastering'),
        ('overdubs', 'Overdubs'),
        ('rehearsal', 'Rehearsal'),
        ('other', 'Other')
    ], string='Service Type', required=True, default='recording')
    
    package_id = fields.Many2one('studio.package', string='Package Deal')
    additional_services = fields.Text(string='Additional Services')
    
    # Equipment
    equipment_ids = fields.Many2many('studio.equipment', string='Additional Equipment')
    equipment_notes = fields.Text(string='Equipment Notes')
    
    # Pricing
    currency_id = fields.Many2one('res.currency', related='room_id.currency_id')
    room_rate = fields.Monetary(string='Room Rate', currency_field='currency_id')
    engineer_rate = fields.Monetary(string='Engineer Rate', currency_field='currency_id')
    equipment_cost = fields.Monetary(string='Equipment Cost', currency_field='currency_id')
    additional_costs = fields.Monetary(string='Additional Costs', currency_field='currency_id')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_totals', store=True)
    tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_totals', store=True)
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_totals', store=True)
    
    # Deposit
    deposit_required = fields.Boolean(string='Deposit Required', default=True)
    deposit_percentage = fields.Float(string='Deposit Percentage (%)', default=50.0)
    deposit_amount = fields.Monetary(string='Deposit Amount', compute='_compute_deposit', store=True)
    deposit_paid = fields.Boolean(string='Deposit Paid', default=False, tracking=True)
    deposit_payment_date = fields.Date(string='Deposit Payment Date')
    
    # Status
    status = fields.Selection([
        ('quote', 'Quote'),
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('in_session', 'In Session'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='quote', required=True, tracking=True)
    
    # Session Details
    project_name = fields.Char(string='Project Name')
    project_description = fields.Text(string='Project Description')
    reference_tracks = fields.Text(string='Reference Tracks/Links')
    special_requirements = fields.Text(string='Special Requirements')
    
    # Files & Deliverables
    session_files = fields.Text(string='Session File Links')
    deliverable_format = fields.Selection([
        ('wav_24_48', 'WAV 24-bit/48kHz'),
        ('wav_24_96', 'WAV 24-bit/96kHz'),
        ('wav_16_44', 'WAV 16-bit/44.1kHz'),
        ('mp3_320', 'MP3 320kbps'),
        ('custom', 'Custom Format')
    ], string='Deliverable Format', default='wav_24_48')
    
    # Invoicing
    invoice_ids = fields.One2many('account.move', 'studio_booking_id', string='Invoices')
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    invoiced = fields.Boolean(string='Invoiced', compute='_compute_invoiced', store=True)
    
    # Contract & Agreement
    service_agreement_signed = fields.Boolean(string='Service Agreement Signed', default=False)
    service_agreement_date = fields.Date(string='Agreement Date')
    service_agreement_doc = fields.Binary(string='Signed Agreement')
    
    # Studio Session Link
    session_ids = fields.One2many('studio.session', 'booking_id', string='Sessions')
    session_count = fields.Integer(string='Session Count', compute='_compute_session_count')
    
    # Reminders
    reminder_24h_sent = fields.Boolean(string='24h Reminder Sent', default=False)
    reminder_2h_sent = fields.Boolean(string='2h Reminder Sent', default=False)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('studio.booking') or _('New')
        return super().create(vals)

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                duration = booking.end_datetime - booking.start_datetime
                booking.duration_hours = duration.total_seconds() / 3600.0
            else:
                booking.duration_hours = 0.0

    @api.depends('room_rate', 'engineer_rate', 'equipment_cost', 'additional_costs')
    def _compute_totals(self):
        for booking in self:
            booking.subtotal = (booking.room_rate + booking.engineer_rate + 
                              booking.equipment_cost + booking.additional_costs)
            # Simplified tax calculation - in production, use proper tax rules
            booking.tax_amount = booking.subtotal * 0.10  # 10% tax
            booking.total_amount = booking.subtotal + booking.tax_amount

    @api.depends('total_amount', 'deposit_percentage')
    def _compute_deposit(self):
        for booking in self:
            if booking.deposit_required:
                booking.deposit_amount = booking.total_amount * (booking.deposit_percentage / 100.0)
            else:
                booking.deposit_amount = 0.0

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for booking in self:
            booking.invoice_count = len(booking.invoice_ids)

    @api.depends('invoice_ids.payment_state')
    def _compute_invoiced(self):
        for booking in self:
            booking.invoiced = any(invoice.payment_state == 'paid' for invoice in booking.invoice_ids)

    @api.depends('session_ids')
    def _compute_session_count(self):
        for booking in self:
            booking.session_count = len(booking.session_ids)

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for booking in self:
            if booking.start_datetime >= booking.end_datetime:
                raise ValidationError(_('End time must be after start time'))
            
            # Check for conflicts with other bookings
            if booking.status in ['confirmed', 'in_session']:
                conflicts = self.search([
                    ('room_id', '=', booking.room_id.id),
                    ('status', 'in', ['confirmed', 'in_session']),
                    ('id', '!=', booking.id),
                    '|',
                    '&', ('start_datetime', '<', booking.end_datetime), 
                         ('end_datetime', '>', booking.start_datetime)
                ])
                if conflicts:
                    raise ValidationError(_('This room is already booked for the selected time period'))

    @api.onchange('room_id', 'duration_hours')
    def _onchange_room_rates(self):
        if self.room_id and self.duration_hours:
            if self.duration_hours >= 8:
                self.room_rate = self.room_id.day_rate or (self.room_id.hourly_rate * 8)
            else:
                self.room_rate = self.room_id.hourly_rate * self.duration_hours

    @api.onchange('engineer_id', 'duration_hours')
    def _onchange_engineer_rate(self):
        if self.engineer_id and self.duration_hours:
            # Get engineer's hourly rate from partner
            self.engineer_rate = self.engineer_id.studio_hourly_rate * self.duration_hours

    def action_confirm_booking(self):
        """Confirm the booking"""
        self.status = 'confirmed'
        self.message_post(body=_('Booking confirmed'))
        
        # Create deposit invoice if required
        if self.deposit_required and not self.deposit_paid:
            self._create_deposit_invoice()
        
        # Schedule reminders
        self._schedule_reminders()

    def action_start_session(self):
        """Start the recording session"""
        self.status = 'in_session'
        self.message_post(body=_('Session started'))
        
        # Create session record
        session_vals = {
            'booking_id': self.id,
            'room_id': self.room_id.id,
            'engineer_id': self.engineer_id.id,
            'client_id': self.client_id.id,
            'project_name': self.project_name,
            'start_time': fields.Datetime.now(),
        }
        self.env['studio.session'].create(session_vals)

    def action_complete_session(self):
        """Complete the booking"""
        self.status = 'completed'
        self.message_post(body=_('Session completed'))
        
        # Create final invoice
        self._create_final_invoice()
        
        # Update session end time
        active_session = self.session_ids.filtered(lambda s: not s.end_time)
        if active_session:
            active_session[0].end_time = fields.Datetime.now()

    def action_cancel_booking(self):
        """Cancel the booking"""
        self.status = 'cancelled'
        self.message_post(body=_('Booking cancelled'))

    def action_mark_no_show(self):
        """Mark as no show"""
        self.status = 'no_show'
        self.message_post(body=_('Client did not show up'))

    def action_create_invoice(self):
        """Create invoice for this booking"""
        return self._create_final_invoice()

    def action_view_invoices(self):
        """View related invoices"""
        return {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('studio_booking_id', '=', self.id)],
        }

    def action_view_sessions(self):
        """View related sessions"""
        return {
            'name': _('Sessions'),
            'type': 'ir.actions.act_window',
            'res_model': 'studio.session',
            'view_mode': 'tree,form',
            'domain': [('booking_id', '=', self.id)],
        }

    def _create_deposit_invoice(self):
        """Create deposit invoice"""
        invoice_vals = {
            'partner_id': self.client_id.id,
            'move_type': 'out_invoice',
            'studio_booking_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'name': f'Deposit for Studio Booking {self.name}',
                'quantity': 1,
                'price_unit': self.deposit_amount,
            })]
        }
        invoice = self.env['account.move'].create(invoice_vals)
        return {
            'name': _('Deposit Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
        }

    def _create_final_invoice(self):
        """Create final invoice"""
        invoice_vals = {
            'partner_id': self.client_id.id,
            'move_type': 'out_invoice',
            'studio_booking_id': self.id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': f'Studio Room {self.room_id.name} - {self.duration_hours}h',
                    'quantity': 1,
                    'price_unit': self.room_rate,
                }),
            ]
        }
        
        # Add engineer line if applicable
        if self.engineer_rate > 0:
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'name': f'Engineer {self.engineer_id.name} - {self.duration_hours}h',
                'quantity': 1,
                'price_unit': self.engineer_rate,
            }))
        
        # Add equipment lines
        if self.equipment_cost > 0:
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'name': 'Additional Equipment',
                'quantity': 1,
                'price_unit': self.equipment_cost,
            }))
        
        invoice = self.env['account.move'].create(invoice_vals)
        return {
            'name': _('Final Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
        }

    def _schedule_reminders(self):
        """Schedule email/SMS reminders"""
        # This would integrate with email templates and optional SMS
        # For now, just log the activity
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            date_deadline=self.start_datetime.date() - timedelta(days=1),
            summary='Send 24h booking reminder',
        )