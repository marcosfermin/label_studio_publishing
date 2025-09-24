# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class LabelDeal(models.Model):
    _name = 'label.deal'
    _description = 'Record Label Deal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Deal Name', required=True, tracking=True)
    deal_number = fields.Char(string='Deal Number', required=True, copy=False, 
                             readonly=True, default=lambda self: _('New'))
    
    # Parties
    party_id = fields.Many2one('res.partner', string='Artist/Writer/Producer', 
                              required=True, tracking=True)
    label_entity_id = fields.Many2one('res.company', string='Label Entity', 
                                     required=True, default=lambda self: self.env.company)
    
    # Deal Classification
    deal_type = fields.Selection([
        ('record', 'Recording Deal'),
        ('publishing', 'Publishing Deal'),
        ('producer', 'Producer Deal'),
        ('360', '360 Deal'),
        ('admin', 'Administration Deal'),
        ('distribution', 'Distribution Deal')
    ], string='Deal Type', required=True, default='record', tracking=True)
    
    # Term & Territory
    term_start = fields.Date(string='Term Start Date', required=True, tracking=True)
    term_end = fields.Date(string='Term End Date', required=True, tracking=True)
    territory = fields.Text(string='Territory', default='Worldwide', required=True)
    exclusivity = fields.Selection([
        ('exclusive', 'Exclusive'),
        ('non_exclusive', 'Non-Exclusive'),
        ('semi_exclusive', 'Semi-Exclusive')
    ], string='Exclusivity', default='exclusive', required=True)
    
    # Options
    option_count = fields.Integer(string='Number of Options', default=0)
    option_exercised_count = fields.Integer(string='Options Exercised', default=0, readonly=True)
    
    # Deliverables
    album_commitment = fields.Integer(string='Album Commitment', default=1)
    single_commitment = fields.Integer(string='Singles Commitment', default=0)
    minimum_commitment = fields.Text(string='Minimum Commitment Details')
    albums_delivered = fields.Integer(string='Albums Delivered', default=0, readonly=True)
    singles_delivered = fields.Integer(string='Singles Delivered', default=0, readonly=True)
    
    # Financial Terms
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    advance_amount = fields.Monetary(string='Advance Amount', tracking=True)
    estimated_value = fields.Monetary(string='Estimated Deal Value')
    
    # Recoupment
    recoupable_advance = fields.Boolean(string='Recoupable Advance', default=True)
    recoup_buckets = fields.Selection([
        ('recording_only', 'Sound Recording Only'),
        ('video_music', 'Video + Music'),
        ('full_cross_collateral', 'Full Cross-Collateralization'),
        ('custom', 'Custom Structure')
    ], string='Recoupment Structure', default='recording_only')
    
    cross_collateralize_releases = fields.Boolean(string='Cross-Collateralize Between Releases', default=False)
    
    # Royalty Rates - Master/Recording
    master_royalty_rate = fields.Float(string='Master Royalty Rate (%)', default=15.0,
                                      help='Artist royalty percentage on master recordings')
    sales_price_basis = fields.Selection([
        ('ppd', 'Published Price to Dealers (PPD)'),
        ('retail', 'Suggested Retail Price'),
        ('net', 'Net Receipts'),
        ('wholesale', 'Wholesale Price')
    ], string='Sales Price Basis', default='ppd')
    
    # Rate Escalations
    escalation_structure = fields.Text(string='Escalation Structure (JSON)', 
                                      help='JSON structure defining rate escalations based on sales thresholds')
    
    # Reserves
    reserve_percentage = fields.Float(string='Reserve Percentage (%)', default=15.0)
    reserve_release_schedule = fields.Selection([
        ('6_months', '6 Months'),
        ('12_months', '12 Months'),
        ('18_months', '18 Months'),
        ('24_months', '24 Months')
    ], string='Reserve Release Schedule', default='12_months')
    
    # Controlled Composition (Mechanical Rights)
    controlled_comp_rate = fields.Float(string='Controlled Composition Rate (%)', default=75.0,
                                       help='Percentage of statutory mechanical rate for controlled compositions')
    mechanical_cap_tracks = fields.Integer(string='Mechanical Cap (# tracks)', default=10,
                                          help='Maximum tracks subject to mechanical royalties per album')
    
    # Publishing (if applicable)
    publishing_admin_fee = fields.Float(string='Publishing Admin Fee (%)', default=15.0)
    writer_share_default = fields.Float(string='Default Writer Share (%)', default=50.0)
    publisher_share_default = fields.Float(string='Default Publisher Share (%)', default=50.0)
    
    # 360 Deal Components (if applicable)
    touring_percentage = fields.Float(string='Touring Revenue Share (%)', default=0.0)
    merchandising_percentage = fields.Float(string='Merchandising Revenue Share (%)', default=0.0)
    sync_percentage = fields.Float(string='Synchronization Revenue Share (%)', default=0.0)
    
    # Contract Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('negotiating', 'Negotiating'),
        ('pending_signature', 'Pending Signature'),
        ('signed', 'Signed'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', required=True, tracking=True)
    
    signed_date = fields.Date(string='Date Signed', tracking=True)
    signature_document_ids = fields.Many2many('documents.document', 
                                             relation='deal_signature_rel',
                                             string='Signed Contracts')
    
    # Source
    source_lead_id = fields.Many2one('label.anr.lead', string='Source A&R Lead', readonly=True)
    
    # Smart Button Counts
    advance_count = fields.Integer(string='Advances Count', compute='_compute_advance_count')
    recoup_balance = fields.Monetary(string='Recoupment Balance', compute='_compute_recoup_balance')
    statement_count = fields.Integer(string='Statements Count', compute='_compute_statement_count')
    catalog_count = fields.Integer(string='Catalog Count', compute='_compute_catalog_count')
    
    # Related Records
    advance_line_ids = fields.One2many('label.deal.advance', 'deal_id', string='Advances')
    recoup_ledger_ids = fields.One2many('royalty.recoup.ledger', 'deal_id', string='Recoupment Ledger')
    
    @api.model
    def create(self, vals):
        if vals.get('deal_number', _('New')) == _('New'):
            vals['deal_number'] = self.env['ir.sequence'].next_by_code('label.deal') or _('New')
        return super().create(vals)

    @api.depends()
    def _compute_advance_count(self):
        for deal in self:
            deal.advance_count = len(deal.advance_line_ids)
    
    @api.depends('recoup_ledger_ids.balance')
    def _compute_recoup_balance(self):
        for deal in self:
            deal.recoup_balance = sum(deal.recoup_ledger_ids.mapped('balance'))
    
    @api.depends()
    def _compute_statement_count(self):
        for deal in self:
            deal.statement_count = self.env['royalty.statement'].search_count([
                ('party_id', '=', deal.party_id.id)
            ])
    
    @api.depends()
    def _compute_catalog_count(self):
        for deal in self:
            # Count releases where this artist is involved
            deal.catalog_count = self.env['music.release'].search_count([
                ('main_artist_ids', 'in', deal.party_id.id)
            ])

    @api.constrains('term_start', 'term_end')
    def _check_term_dates(self):
        for deal in self:
            if deal.term_start and deal.term_end and deal.term_start >= deal.term_end:
                raise ValidationError(_('Term end date must be after term start date.'))

    @api.constrains('master_royalty_rate', 'reserve_percentage')
    def _check_percentages(self):
        for deal in self:
            if not (0 <= deal.master_royalty_rate <= 100):
                raise ValidationError(_('Master royalty rate must be between 0% and 100%.'))
            if not (0 <= deal.reserve_percentage <= 100):
                raise ValidationError(_('Reserve percentage must be between 0% and 100%.'))

    def action_sign_deal(self):
        """Mark deal as signed and activate"""
        self.ensure_one()
        self.write({
            'status': 'signed',
            'signed_date': fields.Date.today()
        })
        
        # Create initial advance if specified
        if self.advance_amount > 0:
            self._create_advance_record()

    def _create_advance_record(self):
        """Create advance record and accounting entries"""
        advance_vals = {
            'deal_id': self.id,
            'description': f'Initial advance - {self.name}',
            'amount': self.advance_amount,
            'date': fields.Date.today(),
            'recoupable': self.recoupable_advance,
        }
        advance = self.env['label.deal.advance'].create(advance_vals)
        
        # Create accounting entry
        advance._create_accounting_entry()

    def action_view_advances(self):
        """Smart button to view advances"""
        return {
            'name': _('Advances'),
            'type': 'ir.actions.act_window',
            'res_model': 'label.deal.advance',
            'view_mode': 'tree,form',
            'domain': [('deal_id', '=', self.id)],
            'context': {'default_deal_id': self.id},
        }

    def action_view_recoup_ledger(self):
        """Smart button to view recoupment ledger"""
        return {
            'name': _('Recoupment Ledger'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.recoup.ledger',
            'view_mode': 'tree,form',
            'domain': [('deal_id', '=', self.id)],
            'context': {'default_deal_id': self.id},
        }

    def action_view_statements(self):
        """Smart button to view royalty statements"""
        return {
            'name': _('Royalty Statements'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.statement',
            'view_mode': 'tree,form',
            'domain': [('party_id', '=', self.party_id.id)],
        }

    def action_view_catalog(self):
        """Smart button to view related catalog"""
        return {
            'name': _('Catalog'),
            'type': 'ir.actions.act_window',
            'res_model': 'music.release',
            'view_mode': 'tree,form',
            'domain': [('main_artist_ids', 'in', self.party_id.id)],
        }

    def get_effective_royalty_rate(self, sales_units=0):
        """Calculate effective royalty rate with escalations"""
        base_rate = self.master_royalty_rate
        
        if not self.escalation_structure:
            return base_rate
        
        try:
            escalations = json.loads(self.escalation_structure)
            for escalation in escalations:
                threshold = escalation.get('threshold', 0)
                rate = escalation.get('rate', base_rate)
                if sales_units >= threshold:
                    base_rate = rate
        except (json.JSONDecodeError, KeyError):
            # Return base rate if escalation structure is invalid
            pass
        
        return base_rate


class LabelDealAdvance(models.Model):
    _name = 'label.deal.advance'
    _description = 'Deal Advance'
    _inherit = ['mail.thread']
    _order = 'date desc'

    deal_id = fields.Many2one('label.deal', string='Deal', required=True, ondelete='cascade')
    description = fields.Char(string='Description', required=True)
    amount = fields.Monetary(string='Amount', required=True, tracking=True)
    currency_id = fields.Many2one(related='deal_id.currency_id')
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    
    # Recoupment
    recoupable = fields.Boolean(string='Recoupable', default=True)
    bucket = fields.Selection([
        ('recording', 'Sound Recording'),
        ('video', 'Video Production'),
        ('tour_support', 'Tour Support'),
        ('marketing', 'Marketing/Promotion'),
        ('other', 'Other')
    ], string='Recoupment Bucket', default='recording')
    
    # Accounting
    account_move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    def action_approve(self):
        """Approve the advance"""
        self.state = 'approved'
    
    def action_pay(self):
        """Mark as paid and create accounting entry"""
        self.state = 'paid'
        if not self.account_move_id:
            self._create_accounting_entry()
            
        # Create recoupment ledger entry if recoupable
        if self.recoupable:
            self._create_recoup_entry()
    
    def _create_accounting_entry(self):
        """Create journal entry for the advance"""
        # This would create the appropriate debit/credit entries
        # Implementation depends on chart of accounts setup
        pass
    
    def _create_recoup_entry(self):
        """Create recoupment ledger entry"""
        recoup_vals = {
            'deal_id': self.deal_id.id,
            'party_id': self.deal_id.party_id.id,
            'bucket': self.bucket,
            'description': f'Advance: {self.description}',
            'debit_amount': self.amount,
            'credit_amount': 0.0,
            'date': self.date,
            'source_advance_id': self.id,
        }
        self.env['royalty.recoup.ledger'].create(recoup_vals)