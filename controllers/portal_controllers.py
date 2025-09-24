# -*- coding: utf-8 -*-

import base64
from collections import defaultdict
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.portal.controllers.portal import get_records_pager
from odoo.tools import groupby as groupbyelem


class LabelStudioPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        """Add label studio specific counters to portal home"""
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        
        # Check if user has portal access to label studio features
        if partner.is_artist or partner.is_writer or partner.is_studio_client:
            
            if 'royalty_statement_count' in counters:
                values['royalty_statement_count'] = request.env['royalty.statement'].search_count([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['draft', 'processing', 'sent', 'approved', 'paid'])
                ]) if self._check_portal_access('royalty.statement') else 0
            
            if 'studio_booking_count' in counters:
                values['studio_booking_count'] = request.env['studio.booking'].search_count([
                    ('client_id', '=', partner.id)
                ]) if self._check_portal_access('studio.booking') else 0
            
            if 'pending_approval_count' in counters:
                approval_count = 0
                if self._check_portal_access('royalty.statement'):
                    approval_count += request.env['royalty.statement'].search_count([
                        ('partner_id', '=', partner.id),
                        ('state', '=', 'sent')
                    ])
                if self._check_portal_access('publ.split'):
                    approval_count += request.env['publ.split'].search_count([
                        ('writer_id', '=', partner.id),
                        ('state', '=', 'pending')
                    ])
                values['pending_approval_count'] = approval_count
        
        return values

    def _check_portal_access(self, model_name):
        """Check if current user has portal access to specific model"""
        try:
            request.env[model_name].check_access_rights('read')
            return True
        except AccessError:
            return False

    # ===================
    # ARTIST/WRITER PORTAL
    # ===================

    @http.route(['/my/royalties', '/my/royalties/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_royalties(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Artist/Writer royalty dashboard"""
        partner = request.env.user.partner_id
        if not (partner.is_artist or partner.is_writer):
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to royalty information.')
            })

        values = self._prepare_portal_layout_values()
        
        # Date filtering
        today = date.today()
        if not date_begin:
            date_begin = today - relativedelta(years=1)
        if not date_end:
            date_end = today

        # Domain for statements
        domain = [
            ('partner_id', '=', partner.id),
            ('period_start', '>=', date_begin),
            ('period_end', '<=', date_end)
        ]

        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'period_start desc'},
            'amount': {'label': _('Amount'), 'order': 'total_amount desc'},
            'status': {'label': _('Status'), 'order': 'state'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Paging
        statement_count = request.env['royalty.statement'].search_count(domain)
        pager = portal_pager(
            url="/my/royalties",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=statement_count,
            page=page,
            step=self._items_per_page
        )

        # Get statements
        statements = request.env['royalty.statement'].search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])

        # Summary statistics
        all_statements = request.env['royalty.statement'].search(domain)
        summary_stats = {
            'total_earnings': sum(stmt.total_amount for stmt in all_statements),
            'total_statements': len(all_statements),
            'pending_approval': len(all_statements.filtered(lambda s: s.state == 'sent')),
            'ytd_earnings': sum(stmt.total_amount for stmt in all_statements.filtered(
                lambda s: s.period_start.year == today.year
            )),
        }

        # Recent activity (last 3 months)
        recent_domain = domain + [('period_start', '>=', today - relativedelta(months=3))]
        recent_usage = request.env['royalty.usage.line'].search([
            '|',
            ('recording_id.main_artist_ids', 'in', [partner.id]),
            ('work_id.writer_ids', 'in', [partner.id]),
            ('period_start', '>=', today - relativedelta(months=3))
        ], limit=10, order='period_start desc')

        values.update({
            'statements': statements,
            'page_name': 'royalty',
            'pager': pager,
            'default_url': '/my/royalties',
            'date_begin': date_begin,
            'date_end': date_end,
            'sortby': sortby,
            'searchbar_sortings': searchbar_sortings,
            'summary_stats': summary_stats,
            'recent_usage': recent_usage,
        })

        return request.render("label_studio_publishing.portal_royalties", values)

    @http.route(['/my/royalties/<int:statement_id>'], type='http', auth="user", website=True)
    def portal_royalty_statement_detail(self, statement_id, **kw):
        """Individual royalty statement detail view"""
        partner = request.env.user.partner_id
        if not (partner.is_artist or partner.is_writer):
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to royalty information.')
            })

        try:
            statement = request.env['royalty.statement'].browse(statement_id)
            if statement.partner_id != partner:
                raise AccessError(_("You can only access your own statements"))
        except (AccessError, UserError):
            return request.render("portal.portal_error", {
                'error_title': _('Statement Not Found'),
                'error_message': _('The requested statement could not be found or you do not have access to it.')
            })

        # Group usage lines by recording/work
        usage_groups = defaultdict(lambda: {
            'lines': [],
            'total_units': 0,
            'total_amount': 0.0,
            'territories': set(),
            'services': set()
        })

        for line in statement.usage_line_ids:
            key = line.recording_id.title if line.recording_id else (line.work_id.title if line.work_id else 'Unmatched')
            usage_groups[key]['lines'].append(line)
            usage_groups[key]['total_units'] += line.units
            usage_groups[key]['total_amount'] += line.net_amount
            if line.territory_code:
                usage_groups[key]['territories'].add(line.territory_code)
            if line.service:
                usage_groups[key]['services'].add(line.service)

        # Convert territories and services sets to lists
        for group in usage_groups.values():
            group['territories'] = list(group['territories'])
            group['services'] = list(group['services'])

        values = {
            'statement': statement,
            'usage_groups': usage_groups,
            'page_name': 'royalty_statement',
        }

        return request.render("label_studio_publishing.portal_royalty_statement_detail", values)

    @http.route(['/my/royalties/<int:statement_id>/approve'], type='http', auth="user", website=True, csrf=True)
    def portal_approve_statement(self, statement_id, **post):
        """Approve royalty statement"""
        partner = request.env.user.partner_id
        statement = request.env['royalty.statement'].browse(statement_id)
        
        if statement.partner_id != partner or statement.state != 'sent':
            return request.render("portal.portal_error", {
                'error_title': _('Cannot Approve'),
                'error_message': _('This statement cannot be approved.')
            })

        # Add approval note if provided
        if post.get('approval_note'):
            statement.message_post(
                body=_("Statement approved by %s. Note: %s") % (partner.name, post.get('approval_note')),
                message_type='comment'
            )

        statement.action_approve()
        
        return request.redirect('/my/royalties/%s?message=approved' % statement_id)

    @http.route(['/my/catalog'], type='http', auth="user", website=True)
    def portal_my_catalog(self, **kw):
        """Artist/Writer catalog view"""
        partner = request.env.user.partner_id
        if not (partner.is_artist or partner.is_writer):
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to catalog information.')
            })

        # Get user's recordings and works
        recordings = request.env['music.recording'].search([
            '|',
            ('main_artist_ids', 'in', [partner.id]),
            ('featured_artist_ids', 'in', [partner.id])
        ])

        works = request.env['music.work'].search([
            ('writer_ids', 'in', [partner.id])
        ])

        releases = request.env['music.release'].search([
            ('recording_ids', 'in', recordings.ids)
        ])

        # Performance stats
        today = date.today()
        ytd_usage = request.env['royalty.usage.line'].search([
            '|',
            ('recording_id', 'in', recordings.ids),
            ('work_id', 'in', works.ids),
            ('period_start', '>=', date(today.year, 1, 1))
        ])

        catalog_stats = {
            'recordings_count': len(recordings),
            'works_count': len(works),
            'releases_count': len(releases),
            'ytd_streams': sum(line.units for line in ytd_usage),
            'ytd_earnings': sum(line.net_amount for line in ytd_usage),
            'territories_count': len(set(line.territory_code for line in ytd_usage if line.territory_code)),
        }

        values = {
            'recordings': recordings,
            'works': works,
            'releases': releases,
            'catalog_stats': catalog_stats,
            'page_name': 'catalog',
        }

        return request.render("label_studio_publishing.portal_catalog", values)

    # ===================
    # STUDIO CLIENT PORTAL
    # ===================

    @http.route(['/my/studio', '/my/studio/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_studio_bookings(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Studio client bookings"""
        partner = request.env.user.partner_id
        if not partner.is_studio_client:
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to studio bookings.')
            })

        values = self._prepare_portal_layout_values()

        # Date filtering
        today = date.today()
        if not date_begin:
            date_begin = today - relativedelta(months=6)
        if not date_end:
            date_end = today + relativedelta(months=6)

        # Domain
        domain = [
            ('client_id', '=', partner.id),
            ('start_date', '>=', date_begin),
            ('start_date', '<=', date_end)
        ]

        # Sorting
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'start_date desc'},
            'room': {'label': _('Room'), 'order': 'room_id'},
            'status': {'label': _('Status'), 'order': 'state'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Paging
        booking_count = request.env['studio.booking'].search_count(domain)
        pager = portal_pager(
            url="/my/studio",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=booking_count,
            page=page,
            step=self._items_per_page
        )

        # Get bookings
        bookings = request.env['studio.booking'].search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])

        # Summary stats
        all_bookings = request.env['studio.booking'].search([('client_id', '=', partner.id)])
        booking_stats = {
            'total_bookings': len(all_bookings),
            'upcoming_bookings': len(all_bookings.filtered(lambda b: b.start_date >= today and b.state == 'confirmed')),
            'total_hours_booked': sum(b.duration for b in all_bookings),
            'total_spent': sum(b.total_amount for b in all_bookings.filtered(lambda b: b.state != 'cancelled')),
        }

        # Available rooms for new bookings
        available_rooms = request.env['studio.room'].search([('active', '=', True)])

        values.update({
            'bookings': bookings,
            'page_name': 'studio_bookings',
            'pager': pager,
            'default_url': '/my/studio',
            'date_begin': date_begin,
            'date_end': date_end,
            'sortby': sortby,
            'searchbar_sortings': searchbar_sortings,
            'booking_stats': booking_stats,
            'available_rooms': available_rooms,
        })

        return request.render("label_studio_publishing.portal_studio_bookings", values)

    @http.route(['/my/studio/<int:booking_id>'], type='http', auth="user", website=True)
    def portal_studio_booking_detail(self, booking_id, **kw):
        """Studio booking detail view"""
        partner = request.env.user.partner_id
        if not partner.is_studio_client:
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to studio bookings.')
            })

        try:
            booking = request.env['studio.booking'].browse(booking_id)
            if booking.client_id != partner:
                raise AccessError(_("You can only access your own bookings"))
        except (AccessError, UserError):
            return request.render("portal.portal_error", {
                'error_title': _('Booking Not Found'),
                'error_message': _('The requested booking could not be found.')
            })

        # Get related sessions
        sessions = request.env['studio.session'].search([
            ('booking_id', '=', booking.id)
        ])

        values = {
            'booking': booking,
            'sessions': sessions,
            'page_name': 'studio_booking',
        }

        return request.render("label_studio_publishing.portal_studio_booking_detail", values)

    @http.route(['/my/studio/request'], type='http', auth="user", website=True, methods=['GET', 'POST'], csrf=True)
    def portal_studio_booking_request(self, **post):
        """Studio booking request form"""
        partner = request.env.user.partner_id
        if not partner.is_studio_client:
            return request.render("portal.portal_error", {
                'error_title': _('Access Denied'),
                'error_message': _('You do not have access to studio bookings.')
            })

        if request.httprequest.method == 'POST':
            # Process booking request
            try:
                values = {
                    'client_id': partner.id,
                    'room_id': int(post.get('room_id')),
                    'start_date': fields.Date.from_string(post.get('start_date')),
                    'end_date': fields.Date.from_string(post.get('end_date')),
                    'start_time': float(post.get('start_time')),
                    'end_time': float(post.get('end_time')),
                    'project_name': post.get('project_name'),
                    'notes': post.get('notes'),
                    'state': 'draft',
                }
                
                if post.get('engineer_id'):
                    values['engineer_id'] = int(post.get('engineer_id'))
                
                booking = request.env['studio.booking'].create(values)
                
                return request.redirect('/my/studio/%s?message=requested' % booking.id)
                
            except Exception as e:
                error_message = str(e)
        else:
            error_message = None

        # GET request - show form
        rooms = request.env['studio.room'].search([('active', '=', True)])
        engineers = request.env['hr.employee'].search([
            ('department_id.name', 'ilike', 'studio'),
            ('active', '=', True)
        ])

        values = {
            'rooms': rooms,
            'engineers': engineers,
            'error_message': error_message,
            'page_name': 'studio_request',
        }

        return request.render("label_studio_publishing.portal_studio_booking_request", values)

    # ===================
    # APPROVALS
    # ===================

    @http.route(['/my/approvals'], type='http', auth="user", website=True)
    def portal_my_approvals(self, **kw):
        """Pending approvals dashboard"""
        partner = request.env.user.partner_id
        
        pending_items = []
        
        # Royalty statements requiring approval
        if partner.is_artist or partner.is_writer:
            pending_statements = request.env['royalty.statement'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'sent')
            ])
            for stmt in pending_statements:
                pending_items.append({
                    'type': 'royalty_statement',
                    'record': stmt,
                    'title': f"Royalty Statement - {stmt.period_start.strftime('%b %Y')}",
                    'amount': stmt.total_amount,
                    'date': stmt.statement_date,
                    'url': f'/my/royalties/{stmt.id}',
                })

        # Split sheets requiring approval
        if partner.is_writer:
            pending_splits = request.env['publ.split'].search([
                ('writer_id', '=', partner.id),
                ('state', '=', 'pending')
            ])
            for split in pending_splits:
                pending_items.append({
                    'type': 'split_sheet',
                    'record': split,
                    'title': f"Split Sheet - {split.work_id.title}",
                    'percentage': split.percentage,
                    'date': split.create_date,
                    'url': f'/my/splits/{split.id}',
                })

        # Sort by date (newest first)
        pending_items.sort(key=lambda x: x['date'], reverse=True)

        values = {
            'pending_items': pending_items,
            'page_name': 'approvals',
        }

        return request.render("label_studio_publishing.portal_approvals", values)

    # ===================
    # DOWNLOADS & EXPORTS
    # ===================

    @http.route(['/my/statement/<int:statement_id>/download'], type='http', auth="user")
    def portal_download_statement(self, statement_id, **kw):
        """Download royalty statement PDF"""
        partner = request.env.user.partner_id
        statement = request.env['royalty.statement'].browse(statement_id)
        
        if statement.partner_id != partner:
            return request.not_found()
        
        # Generate PDF report
        report = request.env.ref('label_studio_publishing.royalty_statement_report')
        pdf_content, _ = report._render_qweb_pdf([statement_id])
        
        filename = f"royalty_statement_{statement.id}_{statement.period_start.strftime('%Y_%m')}.pdf"
        
        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]
        )

    @http.route(['/my/usage/export'], type='http', auth="user", methods=['POST'], csrf=True)
    def portal_export_usage_data(self, **post):
        """Export usage data as CSV"""
        partner = request.env.user.partner_id
        if not (partner.is_artist or partner.is_writer):
            return request.not_found()

        # Get date range
        date_from = fields.Date.from_string(post.get('date_from'))
        date_to = fields.Date.from_string(post.get('date_to'))

        # Get usage lines
        domain = [
            '|',
            ('recording_id.main_artist_ids', 'in', [partner.id]),
            ('work_id.writer_ids', 'in', [partner.id]),
        ]
        if date_from:
            domain.append(('period_start', '>=', date_from))
        if date_to:
            domain.append(('period_end', '<=', date_to))

        usage_lines = request.env['royalty.usage.line'].search(domain)

        # Generate CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Period Start', 'Period End', 'Track', 'Artist', 'Service',
            'Territory', 'Usage Type', 'Units', 'Gross Amount', 'Net Amount'
        ])
        
        # Data
        for line in usage_lines:
            writer.writerow([
                line.period_start.strftime('%Y-%m-%d') if line.period_start else '',
                line.period_end.strftime('%Y-%m-%d') if line.period_end else '',
                line.track_name or '',
                line.artist_name or '',
                line.service or '',
                line.territory_code or '',
                line.usage_type or '',
                line.units or 0,
                line.gross_amount or 0.0,
                line.net_amount or 0.0,
            ])

        filename = f"usage_data_{partner.name.replace(' ', '_')}_{date.today().strftime('%Y_%m_%d')}.csv"
        
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]
        )