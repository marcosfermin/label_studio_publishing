# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RoyaltyUsageLine(models.Model):
    _name = 'royalty.usage.line'
    _description = 'Royalty Usage Line'
    _order = 'period_start desc, id desc'
    _rec_name = 'display_name'

    # Source Information
    source_type = fields.Selection([
        ('distributor', 'Distributor'),
        ('pro', 'Performing Rights Organization'),
        ('publisher', 'Publisher'),
        ('youtube', 'YouTube Content ID'),
        ('spotify', 'Spotify for Artists'),
        ('apple', 'Apple Music for Artists'),
        ('sync', 'Sync License'),
        ('other', 'Other')
    ], string='Source Type', required=True, index=True)
    
    source_id = fields.Many2one('res.partner', string='Source', 
                               help='The distributor, PRO, or other source')
    source_reference = fields.Char(string='Source Reference', index=True)
    
    # Period
    period_start = fields.Date(string='Period Start', required=True, index=True)
    period_end = fields.Date(string='Period End', required=True, index=True)
    reporting_date = fields.Date(string='Reporting Date', default=fields.Date.today)
    
    # Territory & Service
    territory_code = fields.Char(string='Territory Code', size=2, index=True)
    territory_name = fields.Char(string='Territory Name')
    service = fields.Char(string='Service/DSP', index=True,
                         help='Spotify, Apple Music, YouTube, etc.')
    
    # Content Identification
    track_name = fields.Char(string='Track Name', index=True)
    artist_name = fields.Char(string='Artist Name', index=True)
    album_name = fields.Char(string='Album Name')
    label_name = fields.Char(string='Label Name')
    
    # Catalog Codes
    isrc = fields.Char(string='ISRC', index=True)
    iswc = fields.Char(string='ISWC', index=True)
    upc = fields.Char(string='UPC/EAN', index=True)
    
    # Matched Catalog Items
    recording_id = fields.Many2one('music.recording', string='Matched Recording', index=True)
    work_id = fields.Many2one('music.work', string='Matched Work', index=True)
    release_id = fields.Many2one('music.release', string='Matched Release')
    
    # Usage Data
    usage_type = fields.Selection([
        ('stream', 'Stream'),
        ('download', 'Download'),
        ('physical', 'Physical Sale'),
        ('sync', 'Synchronization'),
        ('performance', 'Performance'),
        ('mechanical', 'Mechanical')
    ], string='Usage Type', required=True, index=True)
    
    units = fields.Integer(string='Units/Plays', default=0)
    rate_per_unit = fields.Monetary(string='Rate per Unit', currency_field='currency_id')
    
    # Financial Data
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                 default=lambda self: self.env.company.currency_id)
    gross_amount = fields.Monetary(string='Gross Amount', currency_field='currency_id')
    fees = fields.Monetary(string='Fees/Deductions', currency_field='currency_id', default=0.0)
    net_amount = fields.Monetary(string='Net Amount', currency_field='currency_id',
                                compute='_compute_net_amount', store=True)
    
    # Exchange Rate (if different currency)
    exchange_rate = fields.Float(string='Exchange Rate', default=1.0, digits=(12, 6))
    net_amount_company_currency = fields.Monetary(string='Net Amount (Company Currency)',
                                                 currency_field='company_currency_id',
                                                 compute='_compute_net_amount_company_currency',
                                                 store=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    
    # Matching Status
    matched_state = fields.Selection([
        ('unmatched', 'Unmatched'),
        ('auto_matched', 'Auto Matched'),
        ('manually_matched', 'Manually Matched'),
        ('locked', 'Locked')
    ], string='Matching Status', default='unmatched', required=True, index=True)
    
    confidence_score = fields.Float(string='Matching Confidence', default=0.0,
                                   help='Confidence score for automatic matching (0.0-1.0)')
    
    # Processing
    processed = fields.Boolean(string='Processed', default=False, index=True)
    processed_date = fields.Datetime(string='Processed Date')
    import_batch_id = fields.Char(string='Import Batch ID', index=True)
    
    # Reconciliation
    statement_id = fields.Many2one('royalty.statement', string='Royalty Statement')
    payment_id = fields.Many2one('royalty.payment', string='Payment')
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    @api.depends('gross_amount', 'fees')
    def _compute_net_amount(self):
        for line in self:
            line.net_amount = line.gross_amount - line.fees

    @api.depends('net_amount', 'exchange_rate')
    def _compute_net_amount_company_currency(self):
        for line in self:
            if line.currency_id == line.company_currency_id:
                line.net_amount_company_currency = line.net_amount
            else:
                line.net_amount_company_currency = line.net_amount * line.exchange_rate

    @api.depends('track_name', 'artist_name', 'usage_type', 'period_start', 'net_amount')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.artist_name and line.track_name:
                parts.append(f"{line.artist_name} - {line.track_name}")
            elif line.track_name:
                parts.append(line.track_name)
            
            if line.usage_type:
                parts.append(f"({dict(line._fields['usage_type'].selection)[line.usage_type]})")
            
            if line.period_start:
                parts.append(f"[{line.period_start.strftime('%Y-%m')}]")
            
            if line.net_amount:
                parts.append(f"{line.currency_id.symbol}{line.net_amount:.2f}")
            
            line.display_name = ' '.join(parts) or 'Usage Line'

    @api.constrains('period_start', 'period_end')
    def _check_period_dates(self):
        for line in self:
            if line.period_start > line.period_end:
                raise ValidationError(_('Period start date must be before period end date'))

    @api.constrains('confidence_score')
    def _check_confidence_score(self):
        for line in self:
            if not (0.0 <= line.confidence_score <= 1.0):
                raise ValidationError(_('Confidence score must be between 0.0 and 1.0'))

    def action_auto_match(self):
        """Attempt to automatically match this usage line to catalog items"""
        for line in self:
            if line.matched_state == 'locked':
                continue
            
            # Try to match by ISRC first
            if line.isrc and not line.recording_id:
                recording = self.env['music.recording'].search([('isrc', '=', line.isrc)], limit=1)
                if recording:
                    line.recording_id = recording.id
                    line.work_id = recording.work_id.id if recording.work_id else False
                    line.confidence_score = 1.0
                    line.matched_state = 'auto_matched'
                    continue
            
            # Try to match by ISWC
            if line.iswc and not line.work_id:
                work = self.env['music.work'].search([('iswc', '=', line.iswc)], limit=1)
                if work:
                    line.work_id = work.id
                    line.confidence_score = 1.0
                    line.matched_state = 'auto_matched'
                    continue
            
            # Fuzzy matching by title and artist
            if line.track_name and line.artist_name:
                # This is a simplified version - in production, use proper fuzzy matching
                recordings = self.env['music.recording'].search([
                    ('title', 'ilike', line.track_name),
                    ('main_artist_ids.name', 'ilike', line.artist_name)
                ], limit=5)
                
                if len(recordings) == 1:
                    line.recording_id = recordings.id
                    line.work_id = recordings.work_id.id if recordings.work_id else False
                    line.confidence_score = 0.8  # Lower confidence for fuzzy match
                    line.matched_state = 'auto_matched'

    def action_manual_match_recording(self):
        """Open wizard to manually match to a recording"""
        return {
            'name': _('Manual Match Recording'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.usage.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_usage_line_id': self.id,
                'default_match_type': 'recording'
            }
        }

    def action_manual_match_work(self):
        """Open wizard to manually match to a work"""
        return {
            'name': _('Manual Match Work'),
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.usage.match.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_usage_line_id': self.id,
                'default_match_type': 'work'
            }
        }

    def action_lock_match(self):
        """Lock the current matching to prevent auto-matching"""
        self.matched_state = 'locked'

    def action_reset_match(self):
        """Reset matching state"""
        if self.matched_state != 'locked':
            self.write({
                'recording_id': False,
                'work_id': False,
                'release_id': False,
                'confidence_score': 0.0,
                'matched_state': 'unmatched'
            })

    @api.model
    def auto_match_batch(self, batch_size=1000):
        """Auto-match a batch of unmatched usage lines"""
        unmatched_lines = self.search([
            ('matched_state', '=', 'unmatched'),
            ('processed', '=', False)
        ], limit=batch_size)
        
        unmatched_lines.action_auto_match()
        
        return {
            'processed': len(unmatched_lines),
            'matched': len(unmatched_lines.filtered(lambda l: l.matched_state == 'auto_matched'))
        }

    def get_effective_splits(self):
        """Get effective splits for this usage line"""
        self.ensure_one()
        
        splits = []
        if self.work_id and self.work_id.split_ids:
            # Use work splits for performance/mechanical royalties
            splits = self.work_id.split_ids
        elif self.recording_id:
            # For master recording royalties, use deal terms
            deals = self.env['label.deal'].search([
                ('party_id', 'in', self.recording_id.main_artist_ids.ids),
                ('status', 'in', ['signed', 'active'])
            ])
            # This would return deal-based splits
            
        return splits