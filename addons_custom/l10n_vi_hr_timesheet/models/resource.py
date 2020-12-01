# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT

from datetime import timedelta
from odoo.osv import osv
import pytz
import base64
import calendar
import datetime as dt
import sys
import time
import xlrd


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    @api.model
    def default_get(self, fields):
        res = super(ResourceCalendar, self).default_get(fields)
        if not res.get('name') and res.get('company_id'):
            res['name'] = _('Working Hours of %s') % self.env['res.company'].browse(res['company_id']).name
        return res

    def _get_default_attendance_ids(self):
        res = super(ResourceCalendar, self)._get_default_attendance_ids()
        day_period = self.env['hr.shift'].search([], limit=1)
        hour_from = 0
        hour_to = 0
        if len(day_period) != 0:
            hour_from = day_period.hour_from
            hour_to = day_period.hour_to
        else:
            hour_from = 8.5
            hour_to = 18
        return [
            (0, 0, {'name': _('Monday'), 'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
            (0, 0, {'name': _('Tuesday'), 'dayofweek': '1', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
            (0, 0, {'name': _('Wednesday'), 'dayofweek': '2', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
            (0, 0, {'name': _('Thursday'), 'dayofweek': '3', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
            (0, 0, {'name': _('Friday'), 'dayofweek': '4', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
            (0, 0, {'name': _('Saturday'), 'dayofweek': '5', 'hour_from': hour_from, 'hour_to': hour_to,
                    'day_period_id': day_period.id if len(day_period) > 0 else None}),
        ]

    def _get_default_global_ids(self):
        lang_id = self.env['res.lang'].search([('code', '=', self.env.user.lang)], limit=1)
        if len(lang_id) == 0:
            lang_id = self.env['res.lang'].search([('active', '=', True)], limit=1)
        format = lang_id.date_format + ' ' + lang_id.time_format
        # New year
        new_year_st = (datetime(datetime.now().year, 1, 1, 0, 0, 0, 0)).strftime(DATETIME_FORMAT)
        new_year_en = (datetime(datetime.now().year, 1, 1, 23, 59, 50, 0)).strftime(DATETIME_FORMAT)
        res = [
            (0, 0, {'name': 'New Year', 'date_from': new_year_st,
                    'date_to': new_year_en, 'resource_id': False})
        ]
        return

    global_leave_ids = fields.One2many(
        'resource.calendar.leaves', 'calendar_id', 'Global Leaves',
        domain=[('resource_id', '=', False)], default=_get_default_global_ids)

    attendance_ids = fields.One2many(
        'resource.calendar.attendance', 'calendar_id', 'Working Time',
        copy=True, default=_get_default_attendance_ids)
    file_binary = fields.Binary(string="Upload File")
    file_binary_name = fields.Char()

    @api.multi
    def action_import_leave(self):
        start = time.time()

        # Kiểm tra file rỗng
        if self.file_binary is None:
            raise osv.except_osv('Cảnh báo', 'Vui lòng chon file trước khi import.Xin cảm ơn.')
        # Kiểm tra định dạng file
        self.check_format_file_excel(self.file_binary_name)
        # doc file
        file_import = self.file_binary
        data = base64.decodebytes(file_import)
        excel = xlrd.open_workbook(file_contents=data)
        sheet = excel.sheet_by_index(0)
        index = 1
        vals = []
        while index < sheet.nrows:
            reason = sheet.cell(index, 1).value
            date_from = sheet.cell(index, 2).value
            date_to = sheet.cell(index, 3).value
            date_from = datetime.strptime(date_from, '%d-%m-%Y %H:%M:%S')
            date_to = datetime.strptime(date_to, '%d-%m-%Y %H:%M:%S')
            user_time_zone = self._context.get('tz', False)
            if user_time_zone:
                if user_time_zone.upper() == 'Asia/Ho_Chi_Minh'.upper():
                    offset = timedelta(hours=7)
                else:
                    offset = pytz.timezone(user_time_zone)._utcoffset
            else:
                raise osv.except_osv("Cảnh báo!",
                                     ("Vui lòng cấu hình timezone cho người dùng " + str(self.env.user.name)))
            date_from = date_from - offset
            date_to = date_to - offset
            vals.append({
                'name': reason,
                'date_from': date_from,
                'date_to': date_to,
            })
            index = index + 1
        self.global_leave_ids = vals
        self.file_binary = None
        self.field_binary_name = ''

    @api.multi
    def download_template_leave(self):
        return {
            "type": "ir.actions.act_url",
            "url": '/l10n_vi_hr_timesheet/static/template/leave_template.xls',
            "target": "_parent",
        }

    def check_format_file_excel(self, file_name):
        if file_name == False:
            raise osv.except_osv('Cảnh Báo!', 'Vui lòng kiểm tra lại tên của file trước khi đưa vào hệ thống.')
        if file_name.endswith('.xls') == False and file_name.endswith('.xlsx') == False:
            self.file_binary = None
            self.file_binary_name = None
            raise osv.except_osv("Cảnh báo!",
                                 ("Định dạng file không đúng. Vui lòng đẩy file excel với định dạng: .xlsx or .xls"))


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    day_period = fields.Selection(selection_add=[('none', 'None')], required=False,
                                  default='none')
    day_period_id = fields.Many2one('hr.shift', string="Shift", ondelete="restrict")

    @api.onchange('day_period_id')
    def onchange_day_period(self):
        if self.day_period_id.id:
            self.hour_from = self.day_period_id.hour_from
            self.hour_to = self.day_period_id.hour_to
