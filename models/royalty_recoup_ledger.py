# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RoyaltyRecoupLedger(models.Model):
    _name = 'royalty.recoup.ledger'
    _description = 'Royalty Recoupment Ledger'
    _order = 'date desc, id desc'

    # Deal & Party
    deal_id = fields.Many2one('label.deal', string='Deal', required=True, ondelete='cascade', index=True)
    party_id = fields.Many2one('res.partner', string='Artist/Writer', required=True, index=True)
    
    # Recoupment Bucket
    bucket = fields.Selection([
        ('recording', 'Sound Recording'),
        ('video', 'Video Production'),
        ('tour_support', 'Tour Support'),
        ('marketing', 'Marketing/Promotion'),
        ('other', 'Other')
    ], string='Recoupment Bucket', required=True, index=True)
    
    # Entry Details
    date = fields.Date(string='Date', required=True, default=fields.Date.today, index=True)
    description = fields.Char(string='Description', required=True)
    
    # Amounts
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                 default=lambda self: self.env.company.currency_id)
    debit_amount = fields.Monetary(string='Debit (Advance/Charge)', currency_field='currency_id', default=0.0)
    credit_amount = fields.Monetary(string='Credit (Royalties)', currency_field='currency_id', default=0.0)
    balance = fields.Monetary(string='Running Balance', currency_field='currency_id', 
                             compute='_compute_balance', store=True)
    
    # Source Documents
    source_advance_id = fields.Many2one('label.deal.advance', string='Source Advance')
    source_usage_line_id = fields.Many2one('royalty.usage.line', string='Source Usage Line')
    source_statement_id = fields.Many2one('royalty.statement', string='Source Statement')
    
    # Cross-Collateralization
    cross_collateral_with_ids = fields.Many2many('royalty.recoup.ledger', 
                                                 relation='recoup_cross_collateral_rel',
                                                 column1='ledger_id', column2='cross_ledger_id',
                                                 string='Cross-Collateralized With')
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')
    
    @api.depends('debit_amount', 'credit_amount')
    def _compute_balance(self):
        """Compute running balance for each party/bucket combination"""
        for ledger in self:
            # Get all prior entries for this party and bucket
            prior_entries = self.search([
                ('party_id', '=', ledger.party_id.id),
                ('bucket', '=', ledger.bucket),
                ('date', '<=', ledger.date),
                ('id', '<=', ledger.id)
            ], order='date asc, id asc')
            
            balance = 0.0
            for entry in prior_entries:
                balance += entry.debit_amount - entry.credit_amount
            
            ledger.balance = balance

    @api.model
    def create(self, vals):
        """Override create to recompute balances for affected entries"""
        record = super().create(vals)
        # Recompute balances for all subsequent entries
        self._recompute_balances_after(record)
        return record

    def write(self, vals):
        """Override write to recompute balances if amounts change"""
        result = super().write(vals)
        if 'debit_amount' in vals or 'credit_amount' in vals or 'date' in vals:
            for record in self:
                self._recompute_balances_after(record)
        return result

    def unlink(self):
        """Override unlink to recompute balances after deletion"""
        parties_buckets = [(r.party_id.id, r.bucket) for r in self]
        result = super().unlink()
        # Recompute for affected party/bucket combinations
        for party_id, bucket in parties_buckets:
            self._recompute_balances_for_party_bucket(party_id, bucket)
        return result

    def _recompute_balances_after(self, record):
        """Recompute balances for entries after this record"""
        entries_to_recompute = self.search([
            ('party_id', '=', record.party_id.id),
            ('bucket', '=', record.bucket),
            '|',
            ('date', '>', record.date),
            '&', ('date', '=', record.date), ('id', '>', record.id)
        ], order='date asc, id asc')
        
        entries_to_recompute._compute_balance()

    def _recompute_balances_for_party_bucket(self, party_id, bucket):
        """Recompute all balances for a party/bucket combination"""
        entries = self.search([
            ('party_id', '=', party_id),
            ('bucket', '=', bucket)
        ], order='date asc, id asc')
        
        entries._compute_balance()

    def get_current_balance(self, party_id, bucket, date=None):
        """Get current balance for a party/bucket as of a specific date"""
        domain = [
            ('party_id', '=', party_id),
            ('bucket', '=', bucket),
        ]
        if date:
            domain.append(('date', '<=', date))
        
        entries = self.search(domain)
        return sum(entries.mapped('debit_amount')) - sum(entries.mapped('credit_amount'))

    @api.model
    def create_royalty_credit(self, usage_line, deal, royalty_amount):
        """Create a credit entry for royalty earnings"""
        return self.create({
            'deal_id': deal.id,
            'party_id': deal.party_id.id,
            'bucket': 'recording',  # Default bucket
            'description': f'Royalty earnings - {usage_line.track_name or "Unknown"}',
            'credit_amount': royalty_amount,
            'source_usage_line_id': usage_line.id,
            'date': usage_line.period_end or fields.Date.today(),
        })

    @api.model
    def process_cross_collateralization(self, party_id):
        """Process cross-collateralization between buckets for a party"""
        party = self.env['res.partner'].browse(party_id)
        deals = self.env['label.deal'].search([
            ('party_id', '=', party_id),
            ('cross_collateralize_releases', '=', True),
            ('status', 'in', ['signed', 'active'])
        ])
        
        if not deals:
            return
        
        # Get balances by bucket
        bucket_balances = {}
        for bucket_val, bucket_name in self._fields['bucket'].selection:
            balance = self.get_current_balance(party_id, bucket_val)
            bucket_balances[bucket_val] = balance
        
        # Find positive and negative buckets
        positive_buckets = {k: v for k, v in bucket_balances.items() if v > 0}
        negative_buckets = {k: v for k, v in bucket_balances.items() if v < 0}
        
        # Cross-collateralize positive against negative
        for pos_bucket, pos_amount in positive_buckets.items():
            for neg_bucket, neg_amount in negative_buckets.items():
                if pos_amount <= 0 or neg_amount >= 0:
                    continue
                
                # Transfer amount
                transfer_amount = min(pos_amount, abs(neg_amount))
                
                # Create offsetting entries
                self.create({
                    'deal_id': deals[0].id,  # Use first deal
                    'party_id': party_id,
                    'bucket': pos_bucket,
                    'description': f'Cross-collateralization transfer to {neg_bucket}',
                    'debit_amount': transfer_amount,
                })
                
                self.create({
                    'deal_id': deals[0].id,
                    'party_id': party_id,
                    'bucket': neg_bucket,
                    'description': f'Cross-collateralization transfer from {pos_bucket}',
                    'credit_amount': transfer_amount,
                })
                
                # Update running amounts
                positive_buckets[pos_bucket] -= transfer_amount
                negative_buckets[neg_bucket] += transfer_amount

    def action_view_source_advance(self):
        """View source advance if exists"""
        if self.source_advance_id:
            return {
                'name': _('Source Advance'),
                'type': 'ir.actions.act_window',
                'res_model': 'label.deal.advance',
                'res_id': self.source_advance_id.id,
                'view_mode': 'form',
            }

    def action_view_source_usage(self):
        """View source usage line if exists"""
        if self.source_usage_line_id:
            return {
                'name': _('Source Usage Line'),
                'type': 'ir.actions.act_window',
                'res_model': 'royalty.usage.line',
                'res_id': self.source_usage_line_id.id,
                'view_mode': 'form',
            }

    def name_get(self):
        """Custom name display"""
        result = []
        for ledger in self:
            name = f"{ledger.description}"
            if ledger.debit_amount > 0:
                name = f"{name} (Debit: {ledger.currency_id.symbol}{ledger.debit_amount:.2f})"
            elif ledger.credit_amount > 0:
                name = f"{name} (Credit: {ledger.currency_id.symbol}{ledger.credit_amount:.2f})"
            result.append((ledger.id, name))
        return result