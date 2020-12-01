# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.osv import osv
import base64
import xlrd
import threading
from odoo.exceptions import UserError, except_orm, ValidationError

try:
    import cStringIO as stringIOModule
except ImportError:
    try:
        import StringIO as stringIOModule
    except ImportError:
        import io as stringIOModule

import xlrd
import xlwt
from datetime import datetime, timedelta, date as t_date
import calendar

weekday = {'0': 'Monday',
           '1': 'Tuesday',
           '2': 'Wednesday',
           '3': 'Thursday',
           '4': 'Friday',
           '5': 'Saturday',
           '6': 'Sunday'}


class HrTimesheet(models.Model):
    _name = "hr.timesheet"
    _description = 'Timesheet'

    name = fields.Char(string="Name", default=lambda d: "T ")
    date_from = fields.Date(string="From Date",
                            default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month, 1))
    date_to = fields.Date(string="To Date",
                          default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month,
                                                   calendar.monthrange(datetime.now().date().year,
                                                                       datetime.now().date().month)[1]))
    code = fields.Char(string="Code")
    standard_timesheet_number = fields.Float(string="Standard Timesheet Number")
    not_apply_employee_ids = fields.Many2many('hr.employee', 'hr_timesheet_hr_employee_rel', 'timesheet_id',
                                              'employee_id', string="Not Apply on Employees")
    lines = fields.One2many('hr.timesheet.line', 'timesheet_id', string="Timesheet Employees")
    summaries = fields.One2many('hr.timesheet.line.summary', 'timesheet_id')
    overtimes = fields.One2many('hr.timesheet.line.overtime', 'timesheet_id')
    lates = fields.One2many('hr.timesheet.line.late', 'timesheet_id', domain=[('type', '=', 'late')])
    earlies = fields.One2many('hr.timesheet.line.late', 'timesheet_id', domain=[('type', '=', 'early')])
    leaves = fields.One2many('hr.timesheet.line.leave', 'timesheet_id')
    file_binary = fields.Binary(string="Upload File")
    file_binary_name = fields.Char()
    state = fields.Selection(
        [('draft', 'Draft'), ('calculate', 'Calculate'), ('wait', 'Wait Confirm'), ('confirm', 'Confirm'),
         ('cancel', 'Cancel')], default='draft')
    count_payroll = fields.Integer(string="Count Payroll", compute="_compute_count_payroll")
    payroll_ids = fields.One2many('hr.payroll','timesheet_id', string="Payroll")


    @api.onchange('date_from', 'date_to')
    def _onchange_standard_workday(self):
        for line in self:
            total = line.date_to - line.date_from
            days = total.days + 1
            line.standard_timesheet_number = days - 8
    def _compute_count_payroll(self):
        for record in self:
            record.count_payroll = len(record.payroll_ids)

    def compute_total_mulct_late(self, late_config_id, slip, timesheet_line):
        contract_id = slip.contract_id
        if not contract_id:
            return
        wage = contract_id.wage
        standard_workday = timesheet_line.standard_workday or 26  # cong chuan
        wage_minute = (wage / (standard_workday * 8 * 60))
        wage_day = (wage / (standard_workday * 8))
        money = 0
        for wk in slip.worked_days_line_ids:
            if wk.code == 'LATE':
                if late_config_id.appearance == 'total':
                    money = wk.number_of_minutes * wage_minute * late_config_id.multiplier
                elif late_config_id.appearance == 'count':
                    money = wk.number_of_count * late_config_id.amount
        if late_config_id.appearance == 'code':
            for line in timesheet_line.lates:
                breaking_line_id = self.env['hr.timesheet.break.config.line'].search(
                    [('config_id', '=', late_config_id.id), ('minutes', '>=', line.minutes)], order="minutes", limit=1)
                if len(breaking_line_id) == 0:
                    breaking_line_id = self.env['hr.timesheet.break.config.line'].search(
                        [('config_id', '=', late_config_id.id)], order="minutes desc",
                        limit=1)
                    if len(breaking_line_id) == 0:
                        return
                if breaking_line_id.appearance == 'money':
                    money += breaking_line_id.value
                else:
                    money += breaking_line_id.value * wage_day
        for input in slip.input_line_ids:
            if input.code == 'DED_LATE':
                input.amount = money
                break

    def compute_total_mulct_early(self, late_config_id, slip, timesheet_line):
        contract_id = slip.contract_id
        if not contract_id:
            return
        wage = contract_id.wage
        standard_workday = timesheet_line.standard_workday or 26  # cong chuan
        wage_minute = (wage / (standard_workday * 8 * 60))
        wage_day = (wage / (standard_workday * 8))
        money = 0
        for wk in slip.worked_days_line_ids:
            if wk.code == 'EARLY':
                if late_config_id.appearance == 'total':
                    money = wk.number_of_minutes * wage_minute * late_config_id.multiplier
                elif late_config_id.appearance == 'count':
                    money = wk.number_of_count * late_config_id.amount
        if late_config_id.appearance == 'code':
            for line in timesheet_line.lates:
                breaking_line_id = self.env['hr.timesheet.break.config.line'].search(
                    [('config_id', '=', late_config_id.id), ('minutes', '>=', line.minutes)], order="minutes", limit=1)
                if len(breaking_line_id) == 0:
                    breaking_line_id = self.env['hr.timesheet.break.config.line'].search(
                        [('config_id', '=', late_config_id.id)], order="minutes desc",
                        limit=1)
                    if len(breaking_line_id) == 0:
                        return
                if breaking_line_id.appearance == 'money':
                    money += breaking_line_id.value
                else:
                    money += breaking_line_id.value * wage_day
        for input in slip.input_line_ids:
            if input.code == 'DED_EARLY':
                input.amount = money
                break

    def get_dates_between(self, date_from, date_to):
        result = []
        if date_to < date_from:
            raise osv.except_orm("Cảnh báo!",
                                 "Khoảng thời gian không hợp lệ. Lý do: ngày bắt đầu nhỏ hơn ngày kết thúc. Vui lòng kiểm tra lại. Xin cảm ơn.")
        total = date_to - date_from
        days = total.days
        if days <= 0:
            return
        else:
            for i in range(0, days):
                date_res = date_from + timedelta(days=i)
                result.append(str(date_res))
        return result

    def get_datetime_at_timezone(self, argument):
        result = datetime.strptime(str(argument), '%Y-%m-%d %H:%M:%S')
        result = result + timedelta(hours=7)
        return result

    def get_weekday(self, date):
        return date.weekday()

    def convert_time_to_float(self, time_in):
        total = time_in.hour + time_in.minute / 60 + time_in.second / 3600
        return total

    def get_global_leaves(self, resource_calendar):
        result = {}
        for leave in resource_calendar.global_leave_ids:
            date_from = self.get_datetime_at_timezone(leave.date_from)
            date_to = self.get_datetime_at_timezone(leave.date_to)
            time_in = date_from.time()
            time_out = date_to.time()
            total = (date_to - date_from).days
            if total == 0:
                total = 1
            for i in range(0, total):
                date = date_from + timedelta(days=i)
                result[str(date.date())] = {
                    'name': leave.name,
                    'res_id': leave.id,
                    'date': date.date(),
                    'time_in': time_in,
                    'time_out': time_out,
                }
        return result

    """
    # Kiem tra nhan vien co xin nghi nua ngay hay khong?
    """

    def check_register_early_late(self, date, hours, timesheet_line, type=None):
        if type == 1:
            check_in = date
            check_in = check_in - timedelta(hours=7)
            """
            # xin nghi nua buoi sang
            """
            holiday_id = self.env['hr.leave'].search(
                [('employee_id', '=', timesheet_line.employee_id.id), ('state', '=', 'validate'),
                 ('date_from', '<=', str(check_in)), ('date_to', '>=', str(check_in))], limit=1)
            if len(holiday_id) == 1:
                """
                # Dung la xin nghi buoi sang
                """
                return [1, holiday_id]
            else:
                holiday_id = self.env['hr.leave'].search(
                    [('employee_id', '=', timesheet_line.employee_id.id), ('state', '=', 'validate'),
                     ('date_from', '<=', str(check_in.date())), ('date_to', '>=', str(check_in.date()))], limit=1)
                if len(holiday_id) == 1:
                    """
                    # Xin nghi buoi sang, nhung lai den muon
                    """
                    return [2, holiday_id]
                else:
                    return [0, False]
        elif type == 2:
            check_out = date
            check_out = check_out - timedelta(hours=7)
            """
            # xin nghi nua buoi chieu
            """
            holiday_id = self.env['hr.leave'].search(
                [('employee_id', '=', timesheet_line.employee_id.id), ('state', '=', 'validate'),
                 ('date_from', '<=', str(check_out)), ('date_to', '>=', str(check_out))], limit=1)
            if len(holiday_id) == 1:
                """
                # Dung la xin nghi nua buoi chieu
                """
                return [1, holiday_id]
            else:
                holiday_id = self.env['hr.leave'].search(
                    [('employee_id', '=', timesheet_line.employee_id.id), ('state', '=', 'validate'),
                     ('date_from', '<=', str(check_out.date())), ('date_to', '>=', str(check_out.date()))], limit=1)
                if len(holiday_id) == 1:
                    """
                    # Xin nghi buoi chieu, nhung lai ve som
                    """
                    return [2, holiday_id]
                else:
                    return [0, False]

    """
    # Neu nhan vien duoc nghi, nhung van di lam
    # thi kiem tra xem co phai la ngay le hay ngay nghi binh thuong
    """

    def compute_work_holiday(self, work_dates, timesheet_line, attendance, check_in,
                             check_out, global_leaves, time_in, time_out):
        date = check_in.date()
        # Kiem tra xem hom do co phai la ngay le (hoặc ngày nghỉ đặc biệt) hay khong?
        register_overtime = self.env['hr.register.overtime'].search([('date', '=', date), ('state', '=', 'approve'), ('employee_id', '=', timesheet_line.employee_id.id)])
        # Kiêm tra xem nhân viên có xin đi làm hôm đó khôn
        if register_overtime:
            date_str = str(check_in.date())
            type = None
            if date_str in global_leaves.keys():
                type = 'holiday'
            else:
                type = 'dayoff'
            hours = abs(check_out - check_in)
            self.env['hr.timesheet.line.overtime'].create({
                'timesheet_id': self.id,
                'timesheet_line_id': timesheet_line.id,
                'type': type,
                'employee_id': timesheet_line.employee_id.id,
                'ref_id': attendance.id,
                'hours': hours.seconds / 3600,
                'seconds': hours.seconds,
                'date': date,
                'time_in': time_in,
                'time_out': time_out

            })
            if date_str in work_dates:
                work_dates.remove(date_str)

    def compute_work_daily(self, work_dates, timesheet_line, attendance, calendar, time_in, time_out,
                           check_in, check_out, calendar_attendance):
        date = check_in.date()
        if len(calendar_attendance) == 1:
            """
            # Neu giờ vào và giờ ra hợp lệ.
            """
            if time_in <= calendar_attendance.hour_from and time_out >= calendar_attendance.hour_to:
                """
                # Nhan vien do lam them gio. Quy dinh hon 30 phut la lam them gio
                """
                if abs(calendar_attendance.hour_to - time_out) * 60 >= 30:
                    hours = abs(calendar_attendance.hour_to - time_out)
                    self.env['hr.timesheet.line.overtime'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'type': 'overtime',
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'hours': hours,
                        'seconds': hours * 3600,
                        'date': date,
                        'time_in': calendar_attendance.hour_to,
                        'time_out': time_out
                    })

                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                else:
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })

            elif time_in > calendar_attendance.hour_from and time_out >= calendar_attendance.hour_to:
                """
                # Nhan vien do den muon, ve dung gio
                """

                hours = abs(time_in - calendar_attendance.hour_from)
                result = self.check_register_early_late(check_in, hours, timesheet_line, 1)
                if result[0] == 0:
                    """
                    # Chinh xac la den muon kiểm tra có xin phép đến muộn không
                    """
                    if attendance.result_timekeeping in ['degree', 'yet_approved']:
                        self.env['hr.timesheet.line.late'].create({
                            'timesheet_id': self.id,
                            'timesheet_line_id': timesheet_line.id,
                            'type': 'late',
                            'employee_id': timesheet_line.employee_id.id,
                            'ref_id': attendance.id,
                            'date': date,
                            'time_in': time_in,
                            'time_out': time_out,
                            'minutes': hours
                        })
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                elif result[0] == 1:
                    """
                    # Co xin phep den muon hay: xin nghi nua buoi sang
                    """
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date,
                        'holiday_id': result[1].id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                        'code': 'X/2'
                    })
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X/2',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                elif result[0] == 2:
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date,
                        'holiday_id': result[1].id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                        'code': 'X/2',
                    })
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X/2',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                    if attendance.result_timekeeping in ['degree', 'd']:
                        self.env['hr.timesheet.line.late'].create({
                            'timesheet_id': self.id,
                            'timesheet_line_id': timesheet_line.id,
                            'type': 'late',
                            'employee_id': timesheet_line.employee_id.id,
                            'ref_id': attendance.id,
                            'date': date,
                            'time_in': time_in,
                            'time_out': time_out,
                            'minutes': hours
                        })

            elif time_in <= calendar_attendance.hour_from and time_out < calendar_attendance.hour_to:
                """
                # Nhan vien den dung gio, nhung ve som
                """
                hours = abs(time_out - calendar_attendance.hour_to)
                result = self.check_register_early_late(check_in, hours, timesheet_line, 2)
                if result[0] == 0:
                    if attendance.result_timekeeping in ['degree', 'yet_approved']:
                        self.env['hr.timesheet.line.late'].create({
                            'timesheet_id': self.id,
                            'timesheet_line_id': timesheet_line.id,
                            'type': 'early',
                            'employee_id': timesheet_line.employee_id.id,
                            'ref_id': attendance.id,
                            'date': date,
                            'time_in': time_in,
                            'time_out': time_out,
                            'minutes': hours
                        })
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                elif result[0] == 1:
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date,
                        'holiday_id': result[1].id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                        'code': 'X/2'
                    })
                    if attendance.result_timekeeping in ['degree', 'yet_approved']:
                        self.env['hr.timesheet.line.late'].create({
                            'timesheet_id': self.id,
                            'timesheet_line_id': timesheet_line.id,
                            'type': 'early',
                            'employee_id': timesheet_line.employee_id.id,
                            'ref_id': attendance.id,
                            'date': date,
                            'time_in': time_in,
                            'time_out': time_out,
                            'minutes': hours
                        })

                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X/2',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                elif result[0] == 2:
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date,
                        'holiday_id': result[1].id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                        'code': 'X/2'
                    })
                    self.env['hr.timesheet.line.summary'].create({
                        'timesheet_id': self.id,
                        'timesheet_line_id': timesheet_line.id,
                        'employee_id': timesheet_line.employee_id.id,
                        'ref_id': attendance.id,
                        'code': 'X/2',
                        'date': date,
                        'time_in': time_in,
                        'time_out': time_out
                    })
                    if attendance.result_timekeeping in ['degree', 'yet_approved']:
                        self.env['hr.timesheet.line.late'].create({
                            'timesheet_id': self.id,
                            'timesheet_line_id': timesheet_line.id,
                            'type': 'early',
                            'employee_id': timesheet_line.employee_id.id,
                            'ref_id': attendance.id,
                            'date': date,
                            'time_in': time_in,
                            'time_out': time_out,
                            'minutes': hours
                        })

            elif time_in > calendar_attendance.hour_from and time_out < calendar_attendance.hour_to:
                """
                # Nhan vien vua di muon va vua ve som
                """
                hours = abs(time_out - calendar_attendance.hour_to)
                self.env['hr.timesheet.line.late'].create({
                    'timesheet_id': self.id,
                    'timesheet_line_id': timesheet_line.id,
                    'type': 'early',
                    'employee_id': timesheet_line.employee_id.id,
                    'ref_id': attendance.id,
                    'date': date,
                    'time_in': time_in,
                    'time_out': time_out,
                    'minutes': hours
                })

                hours = abs(time_in - calendar_attendance.hour_from)
                self.env['hr.timesheet.line.late'].create({
                    'timesheet_id': self.id,
                    'timesheet_line_id': timesheet_line.id,
                    'type': 'late',
                    'employee_id': timesheet_line.employee_id.id,
                    'ref_id': attendance.id,
                    'date': date,
                    'time_in': time_in,
                    'time_out': time_out,
                    'minutes': hours
                })
                hr_leave = self.env['hr.leave'].search(
                [('request_date_from', '=', date),('request_date_to', '=', date), ('state', '=', 'validate'), ('request_unit_half', '=', True)])
                if hr_leave:
                    code = 'X/2'
                else:
                    code = 'X'
                if code == 'X/2':
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date,
                        'holiday_id': hr_leave.id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                        'code': 'X/2'
                    })
                self.env['hr.timesheet.line.summary'].create({
                    'timesheet_id': self.id,
                    'timesheet_line_id': timesheet_line.id,
                    'employee_id': timesheet_line.employee_id.id,
                    'ref_id': attendance.id,
                    'code': code,
                    'date': date,
                    'time_in': time_in,
                    'time_out': time_out
                })

            if str(date) in work_dates:
                work_dates.remove(str(date))

    def compute_work_leave(self, work_dates, timesheet_line, calendar, global_leaves):
        for date_str in work_dates:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date_str in global_leaves.keys():
                """
                # Neu do la ngay nghi dac biet
                """
                res_id = global_leaves.get(date_str)
                self.env['hr.timesheet.line.leave'].create({
                    'employee_id': timesheet_line.employee_id.id,
                    'date': date.date(),
                    'resource_leave_id': res_id.get('res_id'),
                    'timesheet_id': timesheet_line.timesheet_id.id,
                    'timesheet_line_id': timesheet_line.id,
                })
            else:
                """
                # Neu khong phai la ngay nghi va nhan vien khong xin nghi
                """
                holiday_id = self.env['hr.leave'].search(
                    [('employee_id', '=', timesheet_line.employee_id.id), ('date_from', '<=', str(date)),
                     ('date_to', '>=', str(date)), ('state', '=', 'validate')])
                if len(holiday_id) == 0:
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date.date(),
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                    })
                else:
                    """
                    # Neu co ngay nghi thi nhan vien do nghi
                    """
                    self.env['hr.timesheet.line.leave'].create({
                        'employee_id': timesheet_line.employee_id.id,
                        'date': date.date(),
                        'holiday_id': holiday_id[0].id,
                        'timesheet_id': timesheet_line.timesheet_id.id,
                        'timesheet_line_id': timesheet_line.id,
                    })

    def action_calculate_timesheet(self):
        work_dates = self.get_dates_between(self.date_from, self.date_to)
        for timesheet in self.lines:
            employee = timesheet.employee_id
            calendar = employee.resource_calendar_id
            if not calendar:
                raise osv.except_orm("Cảnh báo!", "Vui lòng cấu hình ngày làm việc trong nhân viên. Xin cảm ơn.")
            global_leaves = self.get_global_leaves(calendar)
            # Ve mat he thong: Sẽ coi những bản ghi trong hr.attendance là kết quả chấm công cuối cùng.
            attendances = self.env['hr.attendance'].search(
                [('employee_id', '=', employee.id), ('date_in', '>=', self.date_from),
                 ('date_out', '<=', self.date_to)], order="date_in")
            for attendance in attendances:
                check_in = self.get_datetime_at_timezone(attendance.check_in)
                time_in = self.convert_time_to_float(check_in.time())
                check_out = self.get_datetime_at_timezone(attendance.check_out)
                time_out = self.convert_time_to_float(check_out.time())
                date_str = str(check_in.date())
                wk = self.get_weekday(check_in)
                calendar_att_id = self.env['resource.calendar.attendance'].search(
                    [('calendar_id', '=', calendar.id), ('dayofweek', '=', wk)], order="hour_from")
                """
                # Nếu không tìm thấy thời gian làm việc của ngày này
                # thì kiểm tra xem nhân viên đó có đi làm thêm vào ngày nghỉ
                """
                if not calendar_att_id:
                    self.compute_work_holiday(work_dates, timesheet, attendance, check_in,
                                              check_out, global_leaves, time_in, time_out)
                elif date_str in global_leaves.keys():
                    """
                    # Ngay hom do nhan vien duoc nghi le dac biet, nhung van di lam
                    # thi tinh lam tang ca                    
                    """
                    self.compute_work_holiday(work_dates, timesheet, attendance, check_in,
                                              check_out, global_leaves, time_in, time_out)
                else:
                    """
                    # Nếu có lịch làm việc và không phải ngày nghĩ lễ đặc biệt hoặc ngày nghỉ lễ thường
                    # 
                    """
                    self.compute_work_daily(work_dates, timesheet, attendance, calendar, time_in, time_out, check_in,
                                            check_out, calendar_att_id)
            if work_dates:
                """
                # Neu van con ngay lam viec. Kiem tra xem hom do nhan vien co nghi hay khong? 
                # Neu khong nghi va khong phai ngay le thi la nghi khong phep
                """
                self.compute_work_leave(work_dates, timesheet, calendar, global_leaves)

    def action_generate_result_timesheet(self):
        for timesheet in self.lines:
            work_dates = self.get_dates_between(self.date_from, self.date_to)
            employee_id = timesheet.employee_id
            work_real = 0  # cong thuc te
            number_allow_leave = 0 #nghỉ phép
            overtime = 0
            overtime_dayoff = 0
            overtime_holiday = 0
            overtime_not_converted = 0
            late = 0
            early = 0
            leave = 0
            count_holiday_leave = 0
            number_constructor = 0

            summaries = self.env['hr.timesheet.line.summary'].search(
                [('timesheet_id', '=', self.id), ('employee_id', '=', employee_id.id)])
            for line in summaries:
                if line.code == 'X':
                    work_real += 1
                else:
                    work_real += 0.5
            overtimes = self.env['hr.timesheet.line.overtime'].search(
                [('timesheet_id', '=', self.id), ('employee_id', '=', employee_id.id)])
            overtime_id = self.env['hr.timesheet.overtime.config'].search(
                [('active', '=', True), ('state', '=', 'active')], limit=1)
            for line in overtimes:
                # Lay ra cau hinh lam them gio
                if len(overtime_id) == 0:
                    continue
                if employee_id.id in overtime_id.employee_ids.ids:
                    continue
                if employee_id.department_id.id and employee_id.department_id.id in overtime_id.department_ids.ids:
                    continue
                overtime_not_converted += line.hours
                if line.type == 'overtime':
                    overtime += line.hours
                elif line.type == 'dayoff':
                    overtime_dayoff += line.hours
                elif line.type == 'holiday':
                    overtime_holiday += line.hours
                    count_holiday_leave += 1
            lates = self.env['hr.timesheet.line.late'].search(
                [('timesheet_id', '=', self.id), ('employee_id', '=', employee_id.id)])

            # Lay ra cau hinh di muon

            late_id = self.env['hr.timesheet.break.config'].search(
                [('active', '=', True), ('state', '=', 'active'), ('type', '=', 'late')], limit=1)
            if not late_id:
                raise osv.except_orm("Cảnh báo!",
                                     "Vui lòng tạo cấu hình chấm công cho đi muộn. Xin cảm ơn")
            # Lay ra cau hinh ve som
            early_id = self.env['hr.timesheet.break.config'].search(
                [('active', '=', True), ('state', '=', 'active'), ('type', '=', 'early')], limit=1)
            if not early_id:
                raise osv.except_orm("Cảnh báo!",
                                     "Vui lòng tạo cấu hình chấm công cho về sớm. Xin cảm ơn")
            for line in lates:
                if line.type == 'late':
                    if late_id.appearance == 'count' or late_id.appearance == 'code':
                        late += 1
                    else:
                        late += line.minutes
                elif line.type == 'early':
                    if early_id.appearance == 'count' or early_id.appearance == 'code':
                        early += 1
                    else:
                        early += line.minutes

            unreasonal_leave = 0
            allow_leave = 0
            leaves = self.env['hr.timesheet.line.leave'].search(
                [('timesheet_id', '=', self.id), ('employee_id', '=', employee_id.id)])

            for line in leaves:
                if not line.holiday_id and not line.resource_leave_id:
                    unreasonal_leave += 1
                else:
                    if line.code == 'X':
                        allow_leave += 1
                    elif line.code == 'X/2':
                        allow_leave += 0.5
                    else:
                        unreasonal_leave += 1

            # Tính đi công trình
            constructor_ids = self.env['hr.management.constructor'].search(
                [('date_from', '>=', self.date_from),('date_to', '<=', self.date_to), ('state', '=', 'confirm')])

            if len(constructor_ids) > 1:
                raise ValidationError('Bạn đang có %s bảng quản lý đi công trình trong cùng 1 tháng.Vui lòng kiểm tra lại!' %len(constructor_ids))

            for constructor in constructor_ids.management_constructor_ids:
                if constructor.employee_id == employee_id:
                    number_constructor = constructor.number_constructor
            timesheet.number_constructor = number_constructor

            timesheet.real_workday = work_real + number_constructor  #Số ngày đi làm thực tế
            timesheet.number_allow_leave = allow_leave #Nghỉ phép
            timesheet.number_unpaid_leave = (len(work_dates) - timesheet.standard_workday)   # Nghỉ không lương
            timesheet.number_unpaid_leave = 0   # Nghỉ không lương
            timesheet.number_holiday_leave = count_holiday_leave  # Nghỉ lễ
            timesheet.number_unreasonal_leave = (timesheet.standard_workday - (timesheet.real_workday + timesheet.number_allow_leave + timesheet.number_holiday_leave)) - timesheet.number_constructor  #Nghỉ không lý do
            if timesheet.number_unreasonal_leave < 0:
                timesheet.number_unreasonal_leave = 0
            timesheet.late_early = len(lates)  # Đi muộn về sớm
            timesheet.hour_overtime_weekdays = overtime / 8 #Tăng ca ngày thường
            timesheet.hour_overtime_weekend = overtime_dayoff / 8 #Tăng ca cuối tuần
            timesheet.hour_overtime_holidays = overtime_holiday / 8 #Tăng ca ngày lễ
            timesheet.number_lunch = round(work_real)

    @api.multi
    def action_generate_timesheet(self):
        self.lines.unlink()
        employee_ids = self.env['hr.employee'].search(
            [('active', '=', True), ('id', 'not in', self.not_apply_employee_ids.ids)])
        for employee in employee_ids:
            timesheet_line = self.env['hr.timesheet.line'].create({
                'employee_id': employee.id,
                'department_id': employee.department_id.id,
                'timesheet_id': self.id,
                'standard_workday': self.standard_timesheet_number,
            })

    @api.multi
    def action_compute_timesheet(self):
        for line in self.lines:
            line.summaries = None
            line.leaves = None
            line.overtimes = None
            line.lates = None
            line.earlies = None
        self.summaries = None
        self.leaves = None
        self.overtimes = None
        self.lates = None
        self.earlies = None
        """
        # Tinh toan cham cong
        """
        self.action_calculate_timesheet()
        """
        # Xu ly cham cong
        """
        self.action_generate_result_timesheet()
        self.state = 'calculate'

    @api.multi
    def action_download(self):
        """
        # Chuc nang download
        """
        wb = xlwt.Workbook(encoding='UTF-8')
        name_sheet = 'Cập nhật kết quả chấm công'
        ws = wb.add_sheet(name_sheet)

        style_content = xlwt.easyxf(
            "align: horiz center;font:bold True;borders: top thin,right thin,bottom thin,left thin")
        style_head_po = xlwt.easyxf(
            'align: horiz center;font:bold True;pattern: pattern solid;borders: top thin,right thin,bottom thin,left thin')
        style_body = xlwt.easyxf('align: HORZ CENTER, VERT CENTER;borders:top thin,right thin,bottom thin,left thin')

        style = xlwt.XFStyle()
        style.alignment.wrap = 1

        ws.col(0).width = 20 * 210
        ws.col(1).width = 20 * 210
        ws.col(2).width = 20 * 300
        ws.col(3).width = 20 * 300
        ws.col(4).width = 20 * 300
        ws.col(5).width = 20 * 300
        ws.col(6).width = 20 * 300
        ws.col(7).width = 20 * 300
        ws.col(8).width = 20 * 300
        ws.col(9).width = 20 * 300
        ws.col(10).width = 20 * 300
        ws.col(11).width = 20 * 300
        ws.col(12).width = 20 * 300
        ws.col(13).width = 20 * 300
        ws.col(14).width = 20 * 300
        ws.col(15).width = 20 * 300
        ws.col(16).width = 20 * 300

        ws.write(0, 0, u'Mã người lao động', style_content)
        ws.write(0, 1, u'Người lao động', style_content)
        ws.write(0, 2, u'Ngày công thực tế', style_content)
        ws.write(0, 3, u'Nghỉ phép', style_content)
        ws.write(0, 4, u'Ngày lễ', style_content)
        ws.write(0, 5, u'Nghỉ chế độ', style_content)
        ws.write(0, 6, u'Nghỉ ốm', style_content)
        ws.write(0, 7, u'Nghỉ thai sản', style_content)
        ws.write(0, 8, u'Nghỉ không lương', style_content)
        ws.write(0, 9, u'Nghỉ không lí do', style_content)
        ws.write(0, 10, u'Tăng ca thường', style_content)
        ws.write(0, 11, u'Tăng ca chủ nhật', style_content)
        ws.write(0, 12, u'Tăng ca lễ', style_content)
        ws.write(0, 13, u'Số giờ làm ca 3', style_content)
        ws.write(0, 14, u'Số ngày đi công trình', style_content)
        ws.write(0, 15, u'Số bữa ăn trưa', style_content)
        ws.write(0, 16, u'Loại', style_content)

        index = 1
        for line in self.lines:
            if not line.employee_id.x_code:
                raise osv.except_orm("Cảnh báo!",
                                     "Vui lòng cập nhật mã nhân viên cho người lao động " + str(
                                         line.employee_id.name) + " trước khi tiến hành tải về. Xin cảm ơn.")
            if line.type == 'employee':
                type = 'CT'
            elif line.type == 'probation':
                type = 'TV'

            ws.write(index, 0, line.employee_id.x_code, style_body)
            ws.write(index, 1, line.employee_id.name, style_body)
            ws.write(index, 2, line.real_workday, style_body)
            ws.write(index, 3, line.number_allow_leave, style_body)
            ws.write(index, 4, line.number_holiday_leave, style_body)
            ws.write(index, 5, line.number_policy_leave, style_body)
            ws.write(index, 6, line.number_sick_leave, style_body)
            ws.write(index, 7, line.number_maternity_leave, style_body)
            ws.write(index, 8, line.number_unpaid_leave, style_body)
            ws.write(index, 9, line.number_unreasonal_leave, style_body)
            ws.write(index, 10, line.hour_overtime_weekdays, style_body)
            ws.write(index, 11, line.hour_overtime_weekend, style_body)
            ws.write(index, 12, line.hour_overtime_holidays, style_body)
            ws.write(index, 13, line.hour_overtime_shift3, style_body)
            ws.write(index, 14, line.number_constructor, style_body)
            ws.write(index, 15, line.number_lunch, style_body)
            ws.write(index, 16, type, style_body)

            index = index + 1

        file_io = stringIOModule.BytesIO()
        wb.save(file_io)
        xls = file_io.getvalue()

        vals = {
            'name': 'hr.timesheet.xls',
            'datas': base64.b64encode(xls),
            'datas_fname': 'hr.timesheet.xls',
            'type': 'binary',
            'res_model': 'hr.timesheet',
            # 'res_id': self.id,
        }
        file_xls = self.env['ir.attachment'].create(vals)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/' + str(file_xls.id) + '?download=true',
            'target': 'new',
        }

    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def check_format_file_excel(self, file_name):
        if file_name == False:
            raise osv.except_osv('Cảnh Báo!', 'Vui lòng kiểm tra lại tên của file trước khi đưa vào hệ thống.')
        if file_name.endswith('.xls') == False and file_name.endswith('.xlsx') == False:
            self.file_binary = None
            self.file_binary_name = None
            raise osv.except_osv("Cảnh báo!",
                                 ("Định dạng file không đúng. Vui lòng đẩy file excel với định dạng: .xlsx or .xls"))

    @api.multi
    def action_sent_employee(self):
        for timesheet in self.lines:
            employee_id = timesheet.employee_id
            partner_id = employee_id.user_id.partner_id
            if not partner_id:
                partner_id = self.env['res.partner'].search([('email', '=', employee_id.work_email)])
            if not partner_id:
                raise ValidationError('Cảnh báo!', ('Bạn chưa cấu hình email cho nhân viên!'))
            email = employee_id.work_email
            if email:
                mail = self.env['izi.sent.mail.template'].create({
                    'name': 'Bảng công từ ' + str(self.date_from) + ' đến ' + str(self.date_to),
                    'model': 'hr.timesheet.line',
                    'res_id': timesheet.id,
                    # 'partner_id': employee_id.address_home_id.id,
                    'partner_id': partner_id.id,
                    'content': 'Bảng công ',
                    'content_before': 'Nội dung chấm công: ',
                    'content_after': '. Để xem chi tiết, bạn vui lòng click chọn vào button dưới đây. Xin cảm ơn.'
                })
                thread_var = threading.Thread(target=mail.action_send_mail_major(True, True))
                thread_var.start()
        self.state = 'wait'

    @api.multi
    def action_confirm(self):
        self.state = 'confirm'

    @api.multi
    def action_payslip(self):
        if self.count_payroll > 0:
            return
        vals = {
            'name': "%s - %s " % (datetime.now().date().month, datetime.now().date().year),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'timesheet_id': self.id,
            'state': 'draft'
        }
        payroll = self.env['hr.payroll'].create(vals)
        for timesheet_line in self.lines:
            contract = self.env['hr.contract'].sudo().search(
                [('state', 'in', ['open', 'pending']), ('employee_id', '=', timesheet_line.employee_id.id)])
            if len(contract) == 0:
                raise ValidationError(
                    "Không tìm thấy được hợp đồng cho nhân viên %s. Vui lòng kiểm tra lại. Xin cảm ơn" %(timesheet_line.employee_id.name))
            payroll_line_vals = {
                'employee_id': timesheet_line.employee_id.id,
                'department_id': timesheet_line.employee_id.department_id.id,
                'open_date': timesheet_line.employee_id.x_start_date,
                'timesheet_line_id': timesheet_line.id,
                'timesheet_id': timesheet_line.timesheet_id.id,
                'payroll_id': payroll.id
            }
            if len(contract) == 1:
                payroll_line_vals.update(contract_id=contract.id)
            payroll_line = self.env['hr.payroll.line'].create(payroll_line_vals)

        # TODO tra ve form Bang luong
        data_obj = self.env['ir.model.data']
        context = dict(self.env.context).copy()
        view = data_obj.xmlid_to_res_id(
            'izi_hr_nesta_custom.hr_payroll_form_view')
        return {
            'name': _('Payroll'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'hr.payroll',
            'views': [(view, 'form')],
            'res_id': payroll.id,
            'view_id': view,
            'target': 'target',
            'context': context,
        }

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrTimesheet, self).unlink()

    @api.multi
    def download_template(self):
        return {
            "type": "ir.actions.act_url",
            "url": '/izi_hr_nesta_custom/static/template/template_hr_timesheet.xlsx',
            "target": "_parent",
        }

    def _check_format_excel(self, file_name):
        if file_name == False:
            return False
        if file_name.endswith('.xls') or file_name.endswith('.xlsx'):
            return True
        return False

    @api.multi
    def action_import(self):
        try:
            if not self._check_format_excel(self.file_binary_name):
                raise UserError(
                    "File không được tìm thấy hoặc không đúng định dạng. Vui lòng kiểm tra lại định dạng file .xls hoặc .xlsx")
            data = base64.decodebytes(self.file_binary)
            excel = xlrd.open_workbook(file_contents=data)
            sheet = excel.sheet_by_index(0)
            index = 1

            while index < sheet.nrows:
                x_code = str(sheet.cell(index, 0).value).strip()
                employee_id = self.env['hr.employee'].search([('x_code', '=', x_code)])
                if len(employee_id) == 0:
                    raise UserError(_(
                        "Mã nhân viên '%s' ở cột %s dòng %s không tồn tại trong hệ thống. Vui lòng kiểm tra lại.") % (
                                        _(sheet.cell(index, 0).value).strip(), str(0 + 1), str(index)))
                else:
                    timesheet_line = self.env['hr.timesheet.line'].search(
                        [('employee_id', '=', employee_id.id), ('timesheet_id', '=', self.id)], limit=1)

                    standard_workday = self.standard_timesheet_number
                    real_workday = str(sheet.cell(index, 2).value).strip()
                    number_allow_leave = str(sheet.cell(index, 3).value).strip()
                    number_holiday_leave = str(sheet.cell(index, 4).value).strip()
                    number_policy_leave = str(sheet.cell(index, 5).value).strip()
                    number_sick_leave = str(sheet.cell(index, 6).value).strip()
                    number_maternity_leave = str(sheet.cell(index, 7).value).strip()
                    number_unpaid_leave = str(sheet.cell(index, 8).value).strip()
                    number_unreasonal_leave = str(sheet.cell(index, 9).value).strip()
                    hour_overtime_weekdays = str(sheet.cell(index, 10).value).strip()
                    hour_overtime_weekend = str(sheet.cell(index, 11).value).strip()
                    hour_overtime_holidays = str(sheet.cell(index, 12).value).strip()
                    hour_overtime_shift3 = str(sheet.cell(index, 13).value).strip()
                    number_constructor = str(sheet.cell(index, 14).value).strip()
                    number_lunch = str(sheet.cell(index, 15).value).strip()
                    type = sheet.cell(index, 16).value
                    if type.upper() == 'CT':
                        type = 'employee'
                    elif type.upper() == 'TV':
                        type = 'probation'
                    else:
                        raise UserError(_(
                            "Nhập sai loại hợp đồng của nhân viên '%s' ở cột %s dòng %s. Vui lòng kiểm tra lại.") % (
                                            _(sheet.cell(index, 0).value).strip(), str(0 + 1), str(index)))
                    try:
                        standard_workdays = float(standard_workday)
                        real_workdays = float(real_workday)
                        number_allow_leaves = float(number_allow_leave)
                        number_holiday_leaves = float(number_holiday_leave)
                        number_policy_leaves = float(number_policy_leave)
                        number_sick_leaves = float(number_sick_leave)
                        number_unpaid_leaves = float(number_unpaid_leave)
                        number_unreasonal_leaves = float(number_unreasonal_leave)
                        number_maternity_leaves = float(number_maternity_leave)
                        hour_overtime_weekdayss = float(hour_overtime_weekdays)
                        hour_overtime_holidayss = float(hour_overtime_holidays)
                        hour_overtime_weekends = float(hour_overtime_weekend)
                        hour_overtime_shift3s = float(hour_overtime_shift3)
                        number_constructors = float(number_constructor)
                        number_lunchs = float(number_lunch)
                    except ValueError:
                        raise UserError(_(
                            "Tham số truyền vào ở dòng %s không đúng định dạng. Vui lòng kiểm tra lại.") % (str(index)))

                    vals = {
                        'employee_id': employee_id.id,
                        'department_id': employee_id.department_id.id,
                        'standard_workday': standard_workdays,
                        'real_workday': real_workdays,
                        'number_allow_leave': number_allow_leaves,
                        'number_holiday_leave': number_holiday_leaves,
                        'number_policy_leave': number_policy_leaves,
                        'number_sick_leave': number_sick_leaves,
                        'number_maternity_leave': number_maternity_leaves,
                        'number_unpaid_leave': number_unpaid_leaves,
                        'number_unreasonal_leave': number_unreasonal_leaves,
                        'hour_overtime_weekdays': hour_overtime_weekdayss,
                        'hour_overtime_weekend': hour_overtime_weekends,
                        'hour_overtime_holidays': hour_overtime_holidayss,
                        'hour_overtime_shift3': hour_overtime_shift3s,
                        'number_constructor': number_constructors,
                        'number_lunch': number_lunchs,
                        'type': type
                    }
                    if len(timesheet_line) > 0:
                        timesheet_line.write(vals)
                    else:
                        vals.update(timesheet_id=self.id)
                        self.env['hr.timesheet.line'].create(vals)
                index = index + 1

            self.file_binary_name = None
            self.file_binary = None
        except ValueError as e:
            raise UserError("Warning!" + str(e))

    @api.multi
    def action_view_payroll(self):
        payroll_ids = self.mapped('payroll_ids')
        action = self.env.ref('izi_hr_nesta_custom.action_hr_payroll').read()[0]
        if len(payroll_ids) > 0:
            action['domain'] = [('id', 'in', payroll_ids.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

class HrTimesheetLine(models.Model):
    _name = 'hr.timesheet.line'
    _description = 'Timsheet Employee'
    _rec_name = 'timesheet_id'

    @api.multi
    def name_get(self):
        return [(record.id, '%s [%s-%s] %s - %s' % (
        record.id, record.timesheet_id.date_from, record.timesheet_id.date_to, record.employee_id.name,
        record.timesheet_id.name)) for record in self]

    timesheet_id = fields.Many2one('hr.timesheet', string='Timesheet', ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    summaries = fields.One2many('hr.timesheet.line.summary', 'timesheet_line_id')
    overtimes = fields.One2many('hr.timesheet.line.overtime', 'timesheet_line_id')
    lates = fields.One2many('hr.timesheet.line.late', 'timesheet_line_id', domain=[('type', '=', 'late')])
    earlies = fields.One2many('hr.timesheet.line.late', 'timesheet_line_id', domain=[('type', '=', 'early')])
    leaves = fields.One2many('hr.timesheet.line.leave', 'timesheet_line_id')
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string="Department")
    # timesheet for employee
    standard_workday = fields.Float(string="Standard Workday", compute="_compute_standard_workday",
                                    store=True)
    real_workday = fields.Float(string="Real Workday")
    number_allow_leave = fields.Float(string="Number Allow Leave")
    number_holiday_leave = fields.Float(string="Number Holiday Leave")
    number_policy_leave = fields.Float(string="Number Policy Leave")
    number_sick_leave = fields.Float(string="Number Sick Leave")
    number_maternity_leave = fields.Float(string="Number Maternity Leave")
    number_unpaid_leave = fields.Float(string="Number Unpaid Leave")
    number_unreasonal_leave = fields.Float(string="Number Unreasonal Leave")
    # overtime
    hour_overtime_weekdays = fields.Float(string="Hours Overtime Weekdays")
    hour_overtime_weekend = fields.Float(string="Hours Overtime Weekends")
    hour_overtime_holidays = fields.Float(string="Hours Overtime Holidays")
    # type
    type = fields.Selection([('probation', 'Probation'), ('employee', 'Employee')], string="Type", default='employee')
    # overtime for shift 3
    hour_overtime_shift3 = fields.Float(string="Hours Overtime Shift3")
    # For Nesta
    number_constructor = fields.Float(string="Number Constructor")
    number_lunch = fields.Float(string="Number Lunch")
    late_early = fields.Float(string="Đi muộn về sớm")

    @api.depends('timesheet_id.standard_timesheet_number')
    def _compute_standard_workday(self):
        for record in self:
            record.standard_workday = record.timesheet_id.standard_timesheet_number


class HrTimesheetLineSummary(models.Model):
    _name = 'hr.timesheet.line.summary'
    _description = 'Timesheet Employee Summary'

    timesheet_id = fields.Many2one('hr.timesheet', string='Timesheet')
    timesheet_line_id = fields.Many2one('hr.timesheet.line')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date = fields.Date(string="Date")
    code = fields.Char(string="Code")
    ref_id = fields.Many2one('hr.attendance', string="Reference")
    time_in = fields.Float(string="Time In")
    time_out = fields.Float(string="Time Out")


class HrTimesheetLineOvertime(models.Model):
    _name = 'hr.timesheet.line.overtime'
    _description = 'Timesheet Employee Overtime'

    timesheet_line_id = fields.Many2one('hr.timesheet.line')
    timesheet_id = fields.Many2one('hr.timesheet')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    type = fields.Selection([('overtime', 'Overtime'), ('dayoff', 'Dayoff'), ('holiday', 'Holiday')],
                            default='overtime')  # lam them, ngay nghi, ngay le
    ref_id = fields.Many2one('hr.attendance', string="Reference")
    hours = fields.Float(string="Hours")
    seconds = fields.Float(string="Seconds")
    date = fields.Date(string="Date")
    time_in = fields.Float(string="Time In")
    time_out = fields.Float(string="Time Out")


class HrTimesheetLineLater(models.Model):
    _name = 'hr.timesheet.line.late'
    _description = 'Timesheet Employee Late'

    timesheet_line_id = fields.Many2one('hr.timesheet.line')
    timesheet_id = fields.Many2one('hr.timesheet')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    ref_id = fields.Many2one('hr.attendance', string="Reference")
    minutes = fields.Float(string="Minutes")
    type = fields.Selection([('late', 'Late'), ('early', 'Early')], default='late')
    date = fields.Date(string="Date")
    time_in = fields.Float(string="Time In")
    time_out = fields.Float(string="Time Out")


class HrTimesheetLineLeave(models.Model):
    _name = 'hr.timesheet.line.leave'
    _description = 'Timesheet Employee Leave'

    timesheet_line_id = fields.Many2one('hr.timesheet.line')
    timesheet_id = fields.Many2one('hr.timesheet')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date = fields.Date(string="Date")
    holiday_id = fields.Many2one('hr.leave', string="Holidays")
    resource_leave_id = fields.Many2one('resource.calendar.leaves', string="Global Leaves")
    code = fields.Char(string="Code")

class HrTimesheetLineConstructor(models.Model):
    _name = 'hr.timesheet.line.constructor'
    _description = 'Timesheet Employee Constructor'

    timesheet_line_id = fields.Many2one('hr.timesheet.line')
    timesheet_id = fields.Many2one('hr.timesheet')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date = fields.Date(string="Date")
    # holiday_id = fields.Many2one('hr.leave', string="Holidays")
    # resource_leave_id = fields.Many2one('resource.calendar.leaves', string="Global Leaves")
