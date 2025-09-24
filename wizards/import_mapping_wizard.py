# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json


class RoyaltyImportMappingWizard(models.TransientModel):
    _name = 'royalty.import.mapping.wizard'
    _description = 'Import Mapping Configuration Wizard'
    
    import_wizard_id = fields.Many2one('royalty.statement.import', string='Import Wizard', required=True)
    preview_data = fields.Text(string='Preview Data', readonly=True)
    column_mapping = fields.Text(string='Column Mapping (JSON)')
    
    # Available file columns (from preview)
    file_columns = fields.Text(string='File Columns (JSON)', readonly=True)
    
    # Mapping lines for UI
    mapping_line_ids = fields.One2many('royalty.import.mapping.line', 'mapping_wizard_id', 
                                      string='Column Mappings')
    
    # Template management
    save_as_template = fields.Boolean(string='Save as Template')
    template_name = fields.Char(string='Template Name')
    
    @api.model
    def default_get(self, fields_list):
        """Load preview data and initialize mapping lines"""
        res = super().default_get(fields_list)
        
        if 'default_preview_data' in self.env.context:
            preview_data = self.env.context['default_preview_data']
            res['preview_data'] = preview_data
            
            # Parse preview to extract columns
            try:
                preview_json = json.loads(preview_data)
                if preview_json.get('header'):
                    file_columns = preview_json['header']
                    res['file_columns'] = json.dumps(file_columns)
            except:
                pass
        
        return res
    
    @api.model
    def create(self, vals):
        """Create mapping lines after creation"""
        record = super().create(vals)
        record._create_mapping_lines()
        return record
    
    def _create_mapping_lines(self):
        """Create mapping lines for UI based on available fields and columns"""
        if not self.file_columns:
            return
        
        try:
            file_columns = json.loads(self.file_columns)
        except:
            return
        
        # Define available target fields
        target_fields = [
            ('track_name', 'Track Name', True),
            ('artist_name', 'Artist Name', True),
            ('album_name', 'Album Name', False),
            ('isrc', 'ISRC', False),
            ('iswc', 'ISWC', False),
            ('upc', 'UPC/EAN', False),
            ('usage_type', 'Usage Type', False),
            ('service', 'Service/Platform', False),
            ('territory_code', 'Territory Code', False),
            ('units', 'Units/Streams', False),
            ('gross_amount', 'Gross Amount', False),
            ('fees', 'Fees/Deductions', False),
        ]
        
        # Load existing mapping if available
        existing_mapping = {}
        if self.column_mapping:
            try:
                existing_mapping = json.loads(self.column_mapping)
            except:
                pass
        
        # Create mapping lines
        mapping_lines = []
        for field_name, field_label, required in target_fields:
            source_column = existing_mapping.get(field_name, '')
            
            # Try to auto-suggest mapping based on column names
            if not source_column:
                source_column = self._suggest_column_mapping(field_name, file_columns)
            
            mapping_lines.append((0, 0, {
                'target_field': field_name,
                'target_field_label': field_label,
                'source_column': source_column,
                'required': required,
                'file_columns_json': self.file_columns,
            }))
        
        self.mapping_line_ids = mapping_lines
    
    def _suggest_column_mapping(self, target_field, file_columns):
        """Auto-suggest source column based on target field"""
        suggestions = {
            'track_name': ['track', 'song', 'title', 'track name', 'song name', 'track title'],
            'artist_name': ['artist', 'performer', 'artist name', 'main artist'],
            'album_name': ['album', 'release', 'album name', 'release title'],
            'isrc': ['isrc', 'recording code'],
            'iswc': ['iswc', 'work code'],
            'upc': ['upc', 'ean', 'catalog number', 'release code'],
            'usage_type': ['usage', 'usage type', 'type', 'revenue type'],
            'service': ['service', 'platform', 'dsp', 'store'],
            'territory_code': ['territory', 'country', 'region', 'territory code'],
            'units': ['units', 'streams', 'plays', 'quantity'],
            'gross_amount': ['amount', 'gross', 'revenue', 'earnings', 'total'],
            'fees': ['fees', 'commission', 'deduction', 'withholding'],
        }
        
        target_keywords = suggestions.get(target_field, [])
        
        for column in file_columns:
            column_lower = column.lower().strip()
            for keyword in target_keywords:
                if keyword in column_lower or column_lower in keyword:
                    return column
        
        return ''
    
    def action_apply_mapping(self):
        """Apply the configured mapping and return to import wizard"""
        # Build mapping dictionary from lines
        mapping = {}
        required_missing = []
        
        for line in self.mapping_line_ids:
            if line.source_column:
                mapping[line.target_field] = line.source_column
            elif line.required:
                required_missing.append(line.target_field_label)
        
        if required_missing:
            raise UserError(_('Required fields not mapped: %s') % ', '.join(required_missing))
        
        # Save mapping to import wizard
        self.import_wizard_id.column_mapping = json.dumps(mapping)
        
        # Save as template if requested
        if self.save_as_template and self.template_name:
            self._save_as_template(mapping)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'royalty.statement.import',
            'res_id': self.import_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _save_as_template(self, mapping):
        """Save current mapping as template"""
        template_vals = {
            'name': self.template_name,
            'source_type': self.import_wizard_id.source_type,
            'column_mapping': json.dumps(mapping),
            'delimiter': self.import_wizard_id.file_delimiter,
            'has_header': self.import_wizard_id.has_header,
        }
        
        # Check if should be default
        existing_default = self.env['royalty.import.template'].search([
            ('source_type', '=', self.import_wizard_id.source_type),
            ('is_default', '=', True)
        ])
        
        if not existing_default:
            template_vals['is_default'] = True
        
        self.env['royalty.import.template'].create(template_vals)


class RoyaltyImportMappingLine(models.TransientModel):
    _name = 'royalty.import.mapping.line'
    _description = 'Import Mapping Line'
    
    mapping_wizard_id = fields.Many2one('royalty.import.mapping.wizard', string='Mapping Wizard', 
                                       required=True, ondelete='cascade')
    
    target_field = fields.Char(string='Target Field', required=True)
    target_field_label = fields.Char(string='Field Label', required=True)
    source_column = fields.Selection(string='Source Column', selection='_get_source_columns')
    required = fields.Boolean(string='Required')
    
    # Store available columns for dynamic selection
    file_columns_json = fields.Text(string='File Columns JSON')
    
    def _get_source_columns(self):
        """Get available source columns for selection"""
        if not self.file_columns_json:
            return []
        
        try:
            columns = json.loads(self.file_columns_json)
            return [('', 'Not Mapped')] + [(col, col) for col in columns]
        except:
            return [('', 'Not Mapped')]
    
    @api.onchange('source_column')
    def _onchange_source_column(self):
        """Update parent mapping when column changes"""
        pass  # Handled by action_apply_mapping


class RoyaltyExportWizard(models.TransientModel):
    _name = 'royalty.export.wizard'
    _description = 'Royalty Export Wizard'
    
    # Export Type
    export_type = fields.Selection([
        ('usage_lines', 'Usage Lines'),
        ('royalty_statements', 'Royalty Statements'),
        ('recoupment_ledger', 'Recoupment Ledger'),
        ('payment_summary', 'Payment Summary'),
        ('catalog_report', 'Catalog Report'),
    ], string='Export Type', required=True, default='usage_lines')
    
    # Filters
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    partner_ids = fields.Many2many('res.partner', string='Partners')
    source_type = fields.Selection([
        ('distributor', 'Distributor'),
        ('pro', 'Performing Rights Organization'),
        ('publisher', 'Publisher'),
        ('youtube', 'YouTube Content ID'),
        ('spotify', 'Spotify for Artists'),
        ('apple', 'Apple Music for Artists'),
    ], string='Source Type')
    
    # Export Options
    file_format = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ], string='File Format', required=True, default='csv')
    
    include_unmatched = fields.Boolean(string='Include Unmatched Lines', default=True)
    include_matched = fields.Boolean(string='Include Matched Lines', default=True)
    group_by_recording = fields.Boolean(string='Group by Recording')
    
    # Results
    export_data = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)
    
    def action_export_data(self):
        """Execute the export process"""
        if self.export_type == 'usage_lines':
            return self._export_usage_lines()
        elif self.export_type == 'royalty_statements':
            return self._export_royalty_statements()
        elif self.export_type == 'recoupment_ledger':
            return self._export_recoupment_ledger()
        elif self.export_type == 'payment_summary':
            return self._export_payment_summary()
        elif self.export_type == 'catalog_report':
            return self._export_catalog_report()
    
    def _export_usage_lines(self):
        """Export usage lines based on filters"""
        domain = self._build_usage_lines_domain()
        
        lines = self.env['royalty.usage.line'].search(domain)
        
        if not lines:
            raise UserError(_('No data found for the specified criteria'))
        
        # Prepare export data
        export_data = []
        for line in lines:
            row = {
                'Import Batch': line.import_batch_id or '',
                'Source Type': dict(line._fields['source_type'].selection).get(line.source_type, ''),
                'Source': line.source_id.name if line.source_id else '',
                'Period Start': line.period_start.strftime('%Y-%m-%d') if line.period_start else '',
                'Period End': line.period_end.strftime('%Y-%m-%d') if line.period_end else '',
                'Track Name': line.track_name or '',
                'Artist Name': line.artist_name or '',
                'Album Name': line.album_name or '',
                'ISRC': line.isrc or '',
                'Usage Type': line.usage_type or '',
                'Service': line.service or '',
                'Territory': line.territory_code or '',
                'Units': line.units or 0,
                'Gross Amount': line.gross_amount or 0.0,
                'Fees': line.fees or 0.0,
                'Net Amount': line.net_amount or 0.0,
                'Matched State': dict(line._fields['matched_state'].selection).get(line.matched_state, ''),
                'Recording': line.recording_id.title if line.recording_id else '',
                'Work': line.work_id.title if line.work_id else '',
            }
            export_data.append(row)
        
        # Generate file
        filename, file_data = self._generate_export_file(export_data, 'usage_lines')
        
        self.export_filename = filename
        self.export_data = file_data
        
        return self._download_file()
    
    def _build_usage_lines_domain(self):
        """Build domain for usage lines export"""
        domain = []
        
        if self.date_from:
            domain.append(('period_start', '>=', self.date_from))
        if self.date_to:
            domain.append(('period_end', '<=', self.date_to))
        if self.partner_ids:
            domain.append(('source_id', 'in', self.partner_ids.ids))
        if self.source_type:
            domain.append(('source_type', '=', self.source_type))
        
        # Filter by matched state
        matched_states = []
        if self.include_matched:
            matched_states.extend(['auto_matched', 'manually_matched'])
        if self.include_unmatched:
            matched_states.extend(['unmatched', 'conflict'])
        
        if matched_states:
            domain.append(('matched_state', 'in', matched_states))
        
        return domain
    
    def _generate_export_file(self, data, export_name):
        """Generate export file in specified format"""
        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{export_name}_{timestamp}.{self.file_format}"
        
        if self.file_format == 'csv':
            return self._generate_csv(data, filename)
        elif self.file_format == 'xlsx':
            return self._generate_excel(data, filename)
        elif self.file_format == 'json':
            return self._generate_json(data, filename)
    
    def _generate_csv(self, data, filename):
        """Generate CSV file"""
        import csv
        import io
        import base64
        
        output = io.StringIO()
        
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        file_data = base64.b64encode(output.getvalue().encode('utf-8'))
        return filename, file_data
    
    def _generate_excel(self, data, filename):
        """Generate Excel file"""
        try:
            import openpyxl
            from openpyxl import Workbook
            import io
            import base64
            
            wb = Workbook()
            ws = wb.active
            
            if data:
                # Headers
                headers = list(data[0].keys())
                ws.append(headers)
                
                # Data rows
                for row in data:
                    ws.append(list(row.values()))
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            file_data = base64.b64encode(output.read())
            return filename, file_data
            
        except ImportError:
            raise UserError(_('openpyxl library not installed. Cannot generate Excel files.'))
    
    def _generate_json(self, data, filename):
        """Generate JSON file"""
        import json
        import base64
        
        json_data = json.dumps(data, indent=2, default=str)
        file_data = base64.b64encode(json_data.encode('utf-8'))
        return filename, file_data
    
    def _download_file(self):
        """Return file download action"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=export_data&download=true&filename={self.export_filename}',
            'target': 'self',
        }
    
    def _export_royalty_statements(self):
        """Export royalty statements"""
        # Implementation for royalty statements export
        raise UserError(_('Royalty statements export not yet implemented'))
    
    def _export_recoupment_ledger(self):
        """Export recoupment ledger"""
        # Implementation for recoupment ledger export
        raise UserError(_('Recoupment ledger export not yet implemented'))
    
    def _export_payment_summary(self):
        """Export payment summary"""
        # Implementation for payment summary export
        raise UserError(_('Payment summary export not yet implemented'))
    
    def _export_catalog_report(self):
        """Export catalog report"""
        # Implementation for catalog report export
        raise UserError(_('Catalog report export not yet implemented'))