# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RoyaltyStatement(models.Model):
    _name = 'royalty.statement'
    _description = 'Royalty Statement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc, name desc'

    name = fields.Char(
        string='Statement Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True,
    )
    statement_date = fields.Date(
        string='Statement Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    period_start = fields.Date(string='Period Start', required=True, tracking=True)
    period_end = fields.Date(string='Period End', required=True, tracking=True)
    due_date = fields.Date(string='Payment Due Date', tracking=True)

    partner_id = fields.Many2one(
        'res.partner',
        string='Recipient',
        required=True,
        tracking=True,
        domain=['|', ('is_artist', '=', True), ('is_writer', '=', True)],
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

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('processing', 'Processing'),
            ('sent', 'Sent'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    usage_line_ids = fields.One2many(
        'royalty.usage.line',
        'statement_id',
        string='Usage Lines',
    )
    usage_line_count = fields.Integer(
        string='Usage Lines',
        compute='_compute_usage_metrics',
        store=True,
    )

    recoup_entry_ids = fields.One2many(
        'royalty.recoup.ledger',
        'source_statement_id',
        string='Recoupment Entries',
    )
    payment_line_ids = fields.One2many(
        'royalty.payment.line',
        'statement_id',
        string='Payments',
    )
    payment_ids = fields.Many2many(
        'royalty.payment',
        compute='_compute_payment_ids',
        string='Payment Records',
    )

    total_gross_amount = fields.Monetary(
        string='Gross Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_fee_amount = fields.Monetary(
        string='Fees & Deductions',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_net_amount = fields.Monetary(
        string='Net Usage Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    manual_adjustment_amount = fields.Monetary(
        string='Manual Adjustments',
        currency_field='currency_id',
        help='Positive or negative adjustments applied before payout.',
        default=0.0,
    )
    recouped_amount = fields.Monetary(
        string='Recouped Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Amount Payable',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    balance_due = fields.Monetary(
        string='Balance Due',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )

    sent_date = fields.Date(string='Sent Date', tracking=True)
    approved_date = fields.Date(string='Approved Date', tracking=True)
    paid_date = fields.Date(string='Paid Date', tracking=True)
    note = fields.Html(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('royalty.statement') or _('New')
        statements = super().create(vals_list)
        statements._sync_usage_processing_flag()
        return statements

    def write(self, vals):
        res = super().write(vals)
        if 'usage_line_ids' in vals or 'state' in vals:
            self._sync_usage_processing_flag()
        return res

    @api.depends('usage_line_ids')
    def _compute_usage_metrics(self):
        for statement in self:
            statement.usage_line_count = len(statement.usage_line_ids)

    @api.depends(
        'usage_line_ids.gross_amount',
        'usage_line_ids.fees',
        'usage_line_ids.net_amount',
        'manual_adjustment_amount',
        'recoup_entry_ids.debit_amount',
        'recoup_entry_ids.credit_amount',
        'payment_line_ids.amount',
        'payment_line_ids.payment_id.state',
    )
    def _compute_totals(self):
        for statement in self:
            gross_total = sum(statement.usage_line_ids.mapped('gross_amount'))
            fee_total = sum(statement.usage_line_ids.mapped('fees'))
            net_total = sum(statement.usage_line_ids.mapped('net_amount'))
            recoup_total = sum(statement.recoup_entry_ids.mapped('credit_amount')) - sum(
                statement.recoup_entry_ids.mapped('debit_amount')
            )

            payable = net_total - recoup_total + statement.manual_adjustment_amount

            posted_payments = statement.payment_line_ids.filtered(
                lambda line: line.payment_id.state in ('posted', 'reconciled')
            )
            paid_amount = sum(posted_payments.mapped('amount'))

            statement.total_gross_amount = gross_total
            statement.total_fee_amount = fee_total
            statement.total_net_amount = net_total
            statement.recouped_amount = recoup_total
            statement.total_amount = payable
            statement.amount_paid = paid_amount
            statement.balance_due = payable - paid_amount

    @api.depends('payment_line_ids.payment_id')
    def _compute_payment_ids(self):
        for statement in self:
            statement.payment_ids = statement.payment_line_ids.mapped('payment_id')

    def _sync_usage_processing_flag(self):
        for statement in self:
            processed = statement.state in ('processing', 'sent', 'approved', 'paid')
            if statement.usage_line_ids:
                statement.usage_line_ids.write({'processed': processed})

    def _update_payment_state(self):
        for statement in self:
            if statement.state in ('cancelled', 'draft'):
                continue
            currency = statement.currency_id or statement.company_id.currency_id
            if currency and currency.is_zero(statement.balance_due):
                updates = {'state': 'paid'}
                if not statement.paid_date:
                    updates['paid_date'] = fields.Date.context_today(statement)
                statement.write(updates)
            elif statement.state == 'paid' and statement.balance_due:
                statement.write({'state': 'approved', 'paid_date': False})

    def action_set_to_draft(self):
        self.write({'state': 'draft', 'sent_date': False, 'approved_date': False, 'paid_date': False})
        self._sync_usage_processing_flag()

    def action_mark_processing(self):
        self.write({'state': 'processing'})
        self._sync_usage_processing_flag()

    def action_mark_sent(self):
        self.write({'state': 'sent', 'sent_date': fields.Date.context_today(self)})
        self._sync_usage_processing_flag()

    def action_mark_approved(self):
        self.write({'state': 'approved', 'approved_date': fields.Date.context_today(self)})

    def action_mark_paid(self):
        self.write({'state': 'paid', 'paid_date': fields.Date.context_today(self)})
        self._update_payment_state()

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self._sync_usage_processing_flag()

    def action_open_usage_lines(self):
        self.ensure_one()
        return {
            'name': _('Usage Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.usage.line',
            'view_mode': 'tree,form',
            'domain': [('statement_id', '=', self.id)],
            'context': {'default_statement_id': self.id},
        }

    def action_open_payments(self):
        self.ensure_one()
        return {
            'name': _('Royalty Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.payment_ids.ids)],
        }

    @api.constrains('period_start', 'period_end')
    def _check_period_dates(self):
        for statement in self:
            if statement.period_start and statement.period_end and statement.period_start > statement.period_end:
                raise ValidationError(_('The period end must be on or after the start date.'))

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"{self.name or 'royalty_statement'}"

