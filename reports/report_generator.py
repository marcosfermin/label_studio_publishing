# -*- coding: utf-8 -*-

import io
from collections import defaultdict
from datetime import datetime

from odoo import api, models


class ReportRoyaltyStatement(models.AbstractModel):
    _name = 'report.label_studio_publishing.royalty_statement_template'
    _description = 'Royalty Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate report values for royalty statement"""
        statements = self.env['royalty.statement'].browse(docids)
        
        report_data = []
        for statement in statements:
            # Calculate totals by recording/work
            recording_totals = defaultdict(lambda: {
                'units': 0,
                'gross_amount': 0.0,
                'net_amount': 0.0,
                'lines': []
            })
            
            for line in statement.usage_line_ids:
                key = line.recording_id.id if line.recording_id else f"unmatched_{line.id}"
                recording_totals[key]['units'] += line.units
                recording_totals[key]['gross_amount'] += line.gross_amount
                recording_totals[key]['net_amount'] += line.net_amount
                recording_totals[key]['lines'].append(line)
            
            # Prepare statement data
            statement_data = {
                'statement': statement,
                'recording_totals': recording_totals,
                'total_units': sum(rt['units'] for rt in recording_totals.values()),
                'total_gross': sum(rt['gross_amount'] for rt in recording_totals.values()),
                'total_net': sum(rt['net_amount'] for rt in recording_totals.values()),
                'period_label': f"{statement.period_start.strftime('%b %Y')} - {statement.period_end.strftime('%b %Y')}",
            }
            report_data.append(statement_data)
        
        return {
            'doc_ids': docids,
            'doc_model': 'royalty.statement',
            'docs': statements,
            'report_data': report_data,
            'company': self.env.company,
        }


class ReportStudioBookingConfirmation(models.AbstractModel):
    _name = 'report.label_studio_publishing.booking_confirmation_template'
    _description = 'Studio Booking Confirmation Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate report values for booking confirmation"""
        bookings = self.env['studio.booking'].browse(docids)

        report_data = []
        for booking in bookings:
            session_records = booking.session_ids.sorted(lambda s: (s.start_time or s.create_date or datetime.min))
            if session_records:
                sessions = [
                    {
                        'name': session.name,
                        'start_time': session.start_time,
                        'end_time': session.end_time,
                        'duration_hours': session.duration_hours,
                        'engineer': session.engineer_id,
                    }
                    for session in session_records
                ]
            else:
                sessions = [
                    {
                        'name': booking.name,
                        'start_time': booking.start_datetime,
                        'end_time': booking.end_datetime,
                        'duration_hours': booking.duration_hours,
                        'engineer': booking.engineer_id,
                    }
                ]

            equipment_list = [
                {
                    'name': equipment.name,
                    'equipment_type': equipment.equipment_type,
                }
                for equipment in booking.equipment_ids
            ]

            booking_data = {
                'booking': booking,
                'sessions': sessions,
                'equipment_list': equipment_list,
                'total_studio_cost': booking.total_amount - (booking.equipment_cost or 0.0),
                'deposit_due': booking.deposit_amount,
                'balance_due': booking.total_amount - booking.deposit_amount,
            }
            report_data.append(booking_data)

        return {
            'doc_ids': docids,
            'doc_model': 'studio.booking',
            'docs': bookings,
            'report_data': report_data,
            'company': self.env.company,
        }


class ReportRemittanceAdvice(models.AbstractModel):
    _name = 'report.label_studio_publishing.remittance_advice_template'
    _description = 'Royalty Payment Remittance Advice Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate report values for remittance advice"""
        payments = self.env['royalty.payment'].browse(docids)

        report_data = []
        for payment in payments:
            statement_lines = []
            statements = payment.line_ids.mapped('statement_id')

            for line in payment.line_ids:
                statement = line.statement_id
                statement_lines.append({
                    'line': line,
                    'statement': statement,
                    'amount': line.amount,
                    'period_start': statement.period_start,
                    'period_end': statement.period_end,
                    'balance_due': statement.balance_due,
                })

            period_start_dates = [s.period_start for s in statements if s.period_start]
            period_end_dates = [s.period_end for s in statements if s.period_end]
            period_start = min(period_start_dates) if period_start_dates else False
            period_end = max(period_end_dates) if period_end_dates else False

            withholding_tax = getattr(payment, 'withholding_tax', 0.0) or 0.0
            admin_fee = getattr(payment, 'admin_fee', 0.0) or 0.0
            advance_recoupment = getattr(payment, 'advance_recoupment', 0.0) or 0.0
            total_deductions = withholding_tax + admin_fee + advance_recoupment

            payment_data = {
                'payment': payment,
                'statement_lines': statement_lines,
                'total_deductions': total_deductions,
                'net_payment': payment.amount_total - total_deductions,
                'period_label': (
                    f"{period_start.strftime('%b %Y')} - {period_end.strftime('%b %Y')}"
                    if period_start and period_end
                    else False
                ),
                'withholding_tax': withholding_tax,
                'admin_fee': admin_fee,
                'advance_recoupment': advance_recoupment,
            }
            report_data.append(payment_data)

        return {
            'doc_ids': docids,
            'doc_model': 'royalty.payment',
            'docs': payments,
            'report_data': report_data,
            'company': self.env.company,
        }


class ReportCatalogSummary(models.AbstractModel):
    _name = 'report.label_studio_publishing.catalog_summary_template'
    _description = 'Music Catalog Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate catalog summary report"""
        # Get date range from context or use defaults
        date_from = data.get('date_from') if data else None
        date_to = data.get('date_to') if data else None
        
        # Catalog statistics
        catalog_stats = {
            'total_works': self.env['music.work'].search_count([]),
            'total_recordings': self.env['music.recording'].search_count([]),
            'total_releases': self.env['music.release'].search_count([]),
            'active_deals': self.env['label.deal'].search_count([('state', '=', 'active')]),
        }
        
        # Recent releases
        release_domain = []
        if date_from:
            release_domain.append(('release_date', '>=', date_from))
        if date_to:
            release_domain.append(('release_date', '<=', date_to))
        
        recent_releases = self.env['music.release'].search(release_domain, limit=20, order='release_date desc')
        
        # Top performing recordings (by usage)
        usage_domain = []
        if date_from:
            usage_domain.append(('period_start', '>=', date_from))
        if date_to:
            usage_domain.append(('period_end', '<=', date_to))
        
        # Group usage by recording
        usage_lines = self.env['royalty.usage.line'].search(usage_domain)
        recording_performance = defaultdict(lambda: {
            'recording': None,
            'total_units': 0,
            'total_revenue': 0.0,
            'territories': set(),
            'services': set(),
        })
        
        for line in usage_lines.filtered('recording_id'):
            rec_id = line.recording_id.id
            if recording_performance[rec_id]['recording'] is None:
                recording_performance[rec_id]['recording'] = line.recording_id
            
            recording_performance[rec_id]['total_units'] += line.units
            recording_performance[rec_id]['total_revenue'] += line.net_amount
            if line.territory_code:
                recording_performance[rec_id]['territories'].add(line.territory_code)
            if line.service:
                recording_performance[rec_id]['services'].add(line.service)
        
        # Convert to list and sort by revenue
        top_recordings = sorted(
            [data for data in recording_performance.values() if data['recording']],
            key=lambda x: x['total_revenue'],
            reverse=True
        )[:10]
        
        # Artist performance
        artist_performance = defaultdict(lambda: {
            'artist': None,
            'recordings_count': 0,
            'total_revenue': 0.0,
        })
        
        for rec_data in recording_performance.values():
            if rec_data['recording'] and rec_data['recording'].main_artist_ids:
                for artist in rec_data['recording'].main_artist_ids:
                    artist_performance[artist.id]['artist'] = artist
                    artist_performance[artist.id]['recordings_count'] += 1
                    artist_performance[artist.id]['total_revenue'] += rec_data['total_revenue']
        
        top_artists = sorted(
            [data for data in artist_performance.values() if data['artist']],
            key=lambda x: x['total_revenue'],
            reverse=True
        )[:10]
        
        return {
            'doc_ids': [],
            'doc_model': 'music.work',  # Dummy model
            'docs': [],
            'catalog_stats': catalog_stats,
            'recent_releases': recent_releases,
            'top_recordings': top_recordings,
            'top_artists': top_artists,
            'date_from': date_from,
            'date_to': date_to,
            'company': self.env.company,
            'report_date': datetime.now(),
        }


class ReportStudioUtilization(models.AbstractModel):
    _name = 'report.label_studio_publishing.studio_utilization_template'
    _description = 'Studio Utilization Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate studio utilization report"""
        date_from = data.get('date_from') if data else None
        date_to = data.get('date_to') if data else None
        
        # Get all rooms
        rooms = self.env['studio.room'].search([('active', '=', True)])
        
        room_data = []
        for room in rooms:
            # Get bookings in period
            booking_domain = [('room_id', '=', room.id)]
            if date_from:
                booking_domain.append(('start_date', '>=', date_from))
            if date_to:
                booking_domain.append(('end_date', '<=', date_to))
            
            bookings = self.env['studio.booking'].search(booking_domain)
            
            # Calculate utilization
            total_hours_available = room.available_hours or 24 * 7  # Default to 24/7
            if date_from and date_to:
                days_in_period = (date_to - date_from).days + 1
                total_hours_available *= days_in_period
            
            booked_hours = sum(booking.duration for booking in bookings)
            utilization_rate = (booked_hours / total_hours_available * 100) if total_hours_available else 0
            
            # Revenue stats
            total_revenue = sum(booking.total_amount for booking in bookings.filtered(lambda b: b.state != 'cancelled'))
            average_booking_value = total_revenue / len(bookings) if bookings else 0
            
            room_info = {
                'room': room,
                'bookings_count': len(bookings),
                'booked_hours': booked_hours,
                'utilization_rate': utilization_rate,
                'total_revenue': total_revenue,
                'average_booking_value': average_booking_value,
                'confirmed_bookings': bookings.filtered(lambda b: b.state == 'confirmed'),
                'completed_bookings': bookings.filtered(lambda b: b.state == 'completed'),
            }
            room_data.append(room_info)
        
        # Overall statistics
        total_bookings = sum(rd['bookings_count'] for rd in room_data)
        total_revenue = sum(rd['total_revenue'] for rd in room_data)
        average_utilization = sum(rd['utilization_rate'] for rd in room_data) / len(room_data) if room_data else 0
        
        return {
            'doc_ids': [],
            'doc_model': 'studio.room',
            'docs': [],
            'room_data': room_data,
            'total_bookings': total_bookings,
            'total_revenue': total_revenue,
            'average_utilization': average_utilization,
            'date_from': date_from,
            'date_to': date_to,
            'company': self.env.company,
            'report_date': datetime.now(),
        }


class ReportDealSummary(models.AbstractModel):
    _name = 'report.label_studio_publishing.deal_summary_template'
    _description = 'Deal Portfolio Summary Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Generate deal portfolio summary report"""
        # Active deals
        active_deals = self.env['label.deal'].search([('state', '=', 'active')])
        
        # Deal statistics
        deal_stats = {
            'total_active': len(active_deals),
            'total_advance': sum(deal.advance_amount for deal in active_deals),
            'total_unrecouped': sum(deal.unrecouped_balance for deal in active_deals),
            'artist_count': len(active_deals.mapped('artist_id')),
        }
        
        # Deal performance analysis
        deal_performance = []
        for deal in active_deals:
            # Get related royalty data
            usage_lines = self.env['royalty.usage.line'].search([
                ('matched_state', 'in', ['auto_matched', 'manually_matched']),
                '|',
                ('recording_id.deal_id', '=', deal.id),
                ('work_id.deal_id', '=', deal.id),
            ])
            
            total_earnings = sum(line.net_amount for line in usage_lines)
            recoupment_progress = (total_earnings / deal.advance_amount * 100) if deal.advance_amount else 0
            
            deal_info = {
                'deal': deal,
                'total_earnings': total_earnings,
                'recoupment_progress': recoupment_progress,
                'months_since_signing': (datetime.now().date() - deal.signing_date).days / 30.44 if deal.signing_date else 0,
                'recordings_count': len(deal.recording_ids),
                'works_count': len(deal.work_ids),
                'releases_count': len(deal.release_ids),
            }
            deal_performance.append(deal_info)
        
        # Sort by earnings
        deal_performance.sort(key=lambda x: x['total_earnings'], reverse=True)
        
        # Territory analysis
        territory_stats = defaultdict(lambda: {
            'earnings': 0.0,
            'units': 0,
            'deals_count': set(),
        })
        
        for line in self.env['royalty.usage.line'].search([
            ('matched_state', 'in', ['auto_matched', 'manually_matched']),
            ('territory_code', '!=', False),
        ]):
            territory = line.territory_code
            territory_stats[territory]['earnings'] += line.net_amount
            territory_stats[territory]['units'] += line.units
            
            if line.recording_id and line.recording_id.deal_id:
                territory_stats[territory]['deals_count'].add(line.recording_id.deal_id.id)
            elif line.work_id and line.work_id.deal_id:
                territory_stats[territory]['deals_count'].add(line.work_id.deal_id.id)
        
        # Convert to list
        territory_performance = [
            {
                'territory': territory,
                'earnings': stats['earnings'],
                'units': stats['units'],
                'deals_count': len(stats['deals_count']),
            }
            for territory, stats in territory_stats.items()
        ]
        territory_performance.sort(key=lambda x: x['earnings'], reverse=True)
        
        return {
            'doc_ids': [],
            'doc_model': 'label.deal',
            'docs': [],
            'deal_stats': deal_stats,
            'deal_performance': deal_performance[:20],  # Top 20
            'territory_performance': territory_performance[:15],  # Top 15
            'company': self.env.company,
            'report_date': datetime.now(),
        }