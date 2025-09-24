# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RoyaltyPayment(models.Model):
    _name = 'royalty.payment'
    _description = 'Royalty Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, name desc'

    name = fields.Char(
        string='Payment Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True,
    )
    payment_date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Recipient',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain=[('type', 'in', ('bank', 'cash'))],
    )
    payment_method = fields.Selection(
        [
            ('ach', 'ACH Transfer'),
            ('wire', 'Wire Transfer'),
            ('check', 'Check'),
            ('paypal', 'PayPal'),
            ('manual', 'Manual Payment'),
        ],
        string='Payment Method',
        default='ach',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('reconciled', 'Reconciled'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    line_ids = fields.One2many(
        'royalty.payment.line',
        'payment_id',
        string='Statement Allocations',
        copy=True,
    )
    amount_total = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
    )
    statement_count = fields.Integer(
        string='Statements',
        compute='_compute_statement_count',
        store=True,
    )
    memo = fields.Char(string='Payment Memo')
    note = fields.Text(string='Internal Notes')
    account_move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('royalty.payment') or _('New')
        payments = super().create(vals_list)
        payments._sync_partner_from_lines()
        return payments

    def write(self, vals):
        res = super().write(vals)
        if 'line_ids' in vals:
            self._sync_partner_from_lines()
        if 'state' in vals:
            self.mapped('line_ids.statement_id')._update_payment_state()
        return res

    def _sync_partner_from_lines(self):
        for payment in self.filtered(lambda pay: not pay.partner_id and pay.line_ids):
            payment.partner_id = payment.line_ids[0].statement_id.partner_id

    @api.depends('line_ids.amount')
    def _compute_amounts(self):
        for payment in self:
            payment.amount_total = sum(payment.line_ids.mapped('amount'))

    @api.depends('line_ids.statement_id')
    def _compute_statement_count(self):
        for payment in self:
            payment.statement_count = len(payment.line_ids.mapped('statement_id'))

    def action_post(self):
        self.write({'state': 'posted'})
        self.mapped('line_ids.statement_id')._update_payment_state()
        return True

    def action_mark_reconciled(self):
        self.write({'state': 'reconciled'})
        self.mapped('line_ids.statement_id')._update_payment_state()
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        self.mapped('line_ids.statement_id')._update_payment_state()
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self.mapped('line_ids.statement_id')._update_payment_state()
        return True

    def action_open_statements(self):
        self.ensure_one()
        return {
            'name': _('Royalty Statements'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.statement',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.line_ids.mapped('statement_id').ids)],
        }

    @api.constrains('line_ids')
    def _check_partner_consistency(self):
        for payment in self:
            partners = payment.line_ids.mapped('statement_id.partner_id')
            if partners and len(partners) > 1:
                raise ValidationError(_('All statements on a payment must belong to the same partner.'))
            if partners and payment.partner_id and payment.partner_id != partners[0]:
                raise ValidationError(_('The payment partner must match the statement partner.'))


class RoyaltyPaymentLine(models.Model):
    _name = 'royalty.payment.line'
    _description = 'Royalty Payment Allocation'
    _order = 'payment_id, id'

    payment_id = fields.Many2one('royalty.payment', string='Payment', required=True, ondelete='cascade')
    statement_id = fields.Many2one('royalty.statement', string='Statement', required=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', store=True)
    company_id = fields.Many2one('res.company', related='payment_id.company_id', store=True)
    note = fields.Char(string='Notes')

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_('Payment amounts must be positive.'))

    def write(self, vals):
        res = super().write(vals)
        if 'amount' in vals:
            self.mapped('statement_id')._update_payment_state()
        return res

    def unlink(self):
        statements = self.mapped('statement_id')
        res = super().unlink()
        statements._update_payment_state()
        return res
