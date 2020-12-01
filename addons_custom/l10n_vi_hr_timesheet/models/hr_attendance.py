# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import timedelta
from odoo.osv import osv
import pytz
import base64
import calendar
import datetime as dt
import sys
import time
import xlrd


class HrAttendance(models.Model):
    _name = 'hr.attendance'
    _inherit = ["hr.attendance", 'mail.thread', 'mail.activity.mixin']

    date_in = fields.Date(string="Date in", compute='_compute_worked_date', store=True, readonly=True)
    date_out = fields.Date(string="Date out", compute='_compute_worked_date', store=True, readonly=True)
    date = fields.Date(string="Date", compute='_compute_worked_date', store=True, readonly=True)
    hour_in = fields.Float(string="Hour In")
    number_min_late = fields.Float(string="Number minutes Late")
    number_min_early = fields.Float(string="Number minutes Early")
    hour_out = fields.Float(string="Hour Out")
    state = fields.Selection(
        [('late', 'Late'), ('early', 'Early'), ('late_and_early', 'Late and Early'),
         ('except', 'Except'), ('miss_in', 'Missing Check In'), ('miss_out', 'Missing Check Out'), ('done', 'On Time')],
        default='done', string="State", help="""
    'Done': when employee get to work on time.
    'late': when employee was late.
    'early': when employee was come back soon.
    'late_and_early': when employee also late but only early
    'except': other case 
    """)
    reason_confirm = fields.Text(string="Reason")
    result_timekeeping = fields.Selection(
        [('done', 'On Time'),
         ('agree', 'Agree'), ('degree', 'Degree'), ('yet_approved', 'Yet Approved')], string="Result Timekeeping", help="""
    'Done': when employee get to work on time.
    'late': when employee was late.
    'early': when employee was come back soon.
    'late_and_early': when employee also late but only early
    """, default='yet_approved')
    shift_id = fields.Many2one('hr.shift', string="Shift", compute='_onchange_shift')


    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """ Verifies the validity of the attendance record compared to the others from the same employee.
            For the same employee we must have :
                * maximum 1 "open" attendance record (without check_out)
                * no overlapping time slices with previous employee records
        """
        for attendance in self:
            # we take the latest attendance before our check_in time and check it doesn't overlap with ours
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                return
                raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s") % {
                    'empl_name': attendance.employee_id.name,
                    'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(attendance.check_in))),
                })

            if not attendance.check_out:
                # if our attendance is "open" (no check_out), we verify there is no other "open" attendance
                no_check_out_attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_out', '=', False),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if no_check_out_attendances:
                    return
                    raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee hasn't checked out since %(datetime)s") % {
                        'empl_name': attendance.employee_id.name,
                        'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(no_check_out_attendances.check_in))),
                    })
            else:
                # we verify that the latest attendance with check_in time before our check_out time
                # is the same as the one before our check_in time computed before, otherwise it overlaps
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                    return
                    raise exceptions.ValidationError(_("Cannot create new attendance record for %(empl_name)s, the employee was already checked in on %(datetime)s") % {
                        'empl_name': attendance.employee_id.name,
                        'datetime': fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(last_attendance_before_check_out.check_in))),
                    })

    @api.depends('employee_id', 'shift_id')
    def _onchange_shift(self):
        for detail in self:
            if detail.employee_id:
                detail.shift_id = detail.employee_id.x_shift_id.id

    @api.depends('check_in', 'check_out')
    def _compute_worked_date(self):
        for attendance in self:
            if attendance.check_out:
                date_out = datetime.strptime(str(attendance.check_out), '%Y-%m-%d %H:%M:%S')
                date_out = date_out + timedelta(hours=7)
                attendance.date_out = date_out.date()
                attendance.date_in = date_out.date()
            if attendance.check_in:
                date_in = datetime.strptime(str(attendance.check_in), '%Y-%m-%d %H:%M:%S')
                date_in = date_in + timedelta(hours=7)
                attendance.date_in = date_in.date()
                attendance.date = date_in.date()

    def convert_time_to_float(self, hour, minutes):
        return (hour * 60 + minutes) / 60

    def get_time_in(self, check_in, type=None):
        user_time_zone = self._context.get('tz', False)
        offset = 0
        if user_time_zone:
            if user_time_zone.upper() == 'Asia/Ho_Chi_Minh'.upper():
                offset = timedelta(hours=7)
            else:
                offset = pytz.timezone(user_time_zone)._utcoffset
        else:
            offset = timedelta(hours=7)
        check_in = check_in + offset
        if type == 'convert_time':
            f_checkin = self.convert_time_to_float(check_in.hour, check_in.minute)
            return f_checkin
        elif type == 'convert_date':
            return check_in

    def get_time_out(self, check_out, type=None):
        user_time_zone = self._context.get('tz', False)
        offset = 0
        if user_time_zone:
            if user_time_zone.upper() == 'Asia/Ho_Chi_Minh'.upper():
                offset = timedelta(hours=7)
            else:
                offset = pytz.timezone(user_time_zone)._utcoffset
        else:
            offset = timedelta(hours=7)
        check_out = check_out + offset
        if type == 'convert_time':
            f_checkout = self.convert_time_to_float(check_out.hour, check_out.minute)
            return f_checkout
        elif type == 'convert_date':
            return check_out

    def get_check_in(self, check_in, calendar_id):
        f_checkin = self.get_time_in(check_in, 'convert_time')
        check_in = self.get_time_in(check_in, 'convert_date')
        weekday = check_in.date().weekday()
        shift = self.shift_id
        in_vals = {
            'hour_in': f_checkin
        }
        # check time in with config attendance
        if shift.id:
            if f_checkin > shift.hour_from:
                in_vals['state'] = 'late'
                in_vals['number_min_late'] = f_checkin - shift.hour_from
            else:
                in_vals['number_min_late'] = 0
        return in_vals

    def get_check_out(self, check_out, calendar_id):
        f_checkout = self.get_time_out(check_out, 'convert_time')
        check_out = self.get_time_out(check_out, 'convert_date')
        weekday = check_out.date().weekday()
        shift = self.shift_id
        out_vals = {
            'hour_out': f_checkout
        }
        # check time in with config attendance
        if shift.id:
            if f_checkout < shift.hour_to:
                out_vals['state'] = 'early'
                out_vals['number_min_early'] = shift.hour_to - f_checkout
            else:
                out_vals['number_min_early'] = 0
        return out_vals

    @api.model
    def create(self, vals):
        res = super(HrAttendance, self).create(vals)
        calendar_id = res.employee_id.resource_calendar_id
        if not calendar_id:
            raise osv.except_orm("Cảnh báo!",
                                 "Bạn chưa cấu hình lịch làm việc cho nhân viên " + str(res.employee_id.name))
        if res.check_in and not res.check_out:
            in_vals = res.get_check_in(res.check_in, calendar_id)
            in_vals['state'] = 'miss_out'
            res.write(in_vals)
        elif res.check_out and not res.check_in:
            out_vals = res.get_check_out(res.check_out, calendar_id)
            out_vals['state'] = 'miss_in'
            res.write(out_vals)
        elif res.check_in and res.check_out:
            in_vals = res.get_check_in(res.check_in, calendar_id)
            out_vals = res.get_check_out(res.check_out, calendar_id)
            merge_vals = {**in_vals, **out_vals}
            if 'state' in in_vals.keys() and 'state' in out_vals.keys():
                merge_vals['state'] = 'late_and_early'
            elif 'state' not in in_vals.keys() and 'state' not in out_vals.keys():
                merge_vals['result_timekeeping'] = 'done'
            res.write(merge_vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(HrAttendance, self).write(vals)
        calendar_id = self.employee_id.resource_calendar_id
        if not calendar_id:
            raise osv.except_orm("Cảnh báo!",
                                 "Bạn chưa cấu hình lịch làm việc cho nhân viên " + str(self.employee_id.name))
        if 'check_in' in vals.keys() and vals.get('check_in') and 'check_out' not in vals.keys():
            in_vals = self.get_check_in(self.check_in, calendar_id)
            if 'state' in in_vals.keys() and self.state == 'early':
                in_vals['state'] = 'late_and_early'
                in_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' in in_vals.keys() and (self.state == 'miss_out' or not self.check_out):
                in_vals['state'] = 'miss_out'
                in_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' not in in_vals.keys() and self.state == 'late_and_early' and self.number_min_early >= 0:
                if self.number_min_early > 0:
                    in_vals['state'] = 'early'
                    in_vals['result_timekeeping'] = 'yet_approved'
                else:
                    in_vals['state'] = 'done'
                    in_vals['result_timekeeping'] = 'done'
            elif 'state' not in in_vals.keys() and self.state == 'late':
                in_vals['state'] = 'done'
                in_vals['result_timekeeping'] = 'done'
            elif 'state' not in in_vals.keys() and self.state == 'miss_out':
                in_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' in in_vals.keys():
                in_vals['result_timekeeping'] = 'yet_approved'
            # if 'state' not in in_vals.keys() and not self.check_out:
            #     in_vals['state'] = 'except'
            # elif 'state' not in in_vals.keys() and self.check_out:
            #     in_vals['state'] = 'done'
            self.write(in_vals)
        elif 'check_in' in vals.keys() and not vals.get('check_in') and 'check_out' not in vals.keys():
            in_vals = {'state': 'miss_in', 'result_timekeeping': 'yet_approved', 'number_min_late': 0, 'hour_in': 0}
            self.write(in_vals)
        elif 'check_out' in vals.keys() and vals.get('check_out') and 'check_in' not in vals.keys():
            out_vals = self.get_check_out(self.check_out, calendar_id)
            if 'state' in out_vals.keys() and self.state == 'late':
                out_vals['state'] = 'late_and_early'
                out_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' in out_vals.keys() and self.state == 'miss_out' and self.number_min_late > 0:
                out_vals['state'] = 'late_and_early'
                out_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' not in out_vals.keys() and self.state == 'late_and_early' and self.number_min_late >= 0:
                if self.number_min_late > 0:
                    out_vals['state'] = 'late'
                    out_vals['result_timekeeping'] = 'yet_approved'
                else:
                    out_vals['state'] = 'done'
                    out_vals['result_timekeeping'] = 'done'
            elif 'state' not in out_vals.keys() and self.state == 'early':
                out_vals['state'] = 'miss_in'
                if not self.check_in:
                    out_vals['state'] = 'miss_in'
                else:
                    out_vals['state'] = 'done'
                    out_vals['result_timekeeping'] = 'done'
            elif 'state' not in out_vals.keys() and self.state == 'miss_out' and self.number_min_late >= 0:
                if self.number_min_late > 0:
                    out_vals['state'] = 'late'
                    out_vals['result_timekeeping'] = 'yet_approved'
                else:
                    out_vals['state'] = 'done'
                    out_vals['result_timekeeping'] = 'done'
            elif 'state' in out_vals.keys():
                out_vals['result_timekeeping'] = 'yet_approved'
            if 'state' not in out_vals.keys() and not self.check_in:
                out_vals['state'] = 'miss_in'
            elif 'state' not in out_vals.keys() and self.check_in:
                out_vals['state'] = 'done'
            self.write(out_vals)
        elif 'check_out' in vals.keys() and not vals.get('check_out') and 'check_in' not in vals.keys():
            out_vals = {'state': 'miss_out', 'result_timekeeping': 'yet_approved', 'number_min_early': 0, 'hour_out': 0}
            self.write(out_vals)
        elif 'check_in' in vals.keys() and 'check_out' in vals.keys():
            in_vals = {}
            out_vals = {}
            if self.check_in:
                in_vals = self.get_check_in(self.check_in, calendar_id)
            if self.check_out:
                out_vals = self.get_check_out(self.check_out, calendar_id)
            merge_vals = {**in_vals, **out_vals}
            if 'state' in in_vals.keys() and 'state' in out_vals.keys():
                merge_vals['state'] = 'late_and_early'
                merge_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' not in in_vals.keys() and 'state' not in out_vals.keys():
                if self.check_out:
                    merge_vals['state'] = 'done'
                    merge_vals['result_timekeeping'] = 'done'
                    merge_vals['number_min_late'] = 0
                    merge_vals['number_min_early'] = 0
                else:
                    merge_vals['state'] = 'miss_out'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['number_min_late'] = 0
                    merge_vals['number_min_early'] = 0
            elif 'state' in in_vals.keys() and 'state' not in out_vals.keys():
                if not self.check_out:
                    merge_vals['state'] = 'miss_out'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['hour_out'] = 0
                    merge_vals['number_min_early'] = 0
                else:
                    merge_vals['number_min_early'] = 0
                    merge_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' in out_vals.keys() and 'state' not in in_vals.keys():
                if not self.check_in:
                    merge_vals['state'] = 'miss_in'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['hour_in'] = 0
                    merge_vals['number_min_late'] = 0
                else:
                    merge_vals['number_min_late'] = 0
                    merge_vals['result_timekeeping'] = 'yet_approved'
            self.write(merge_vals)
        return res

    @api.multi
    def action_agree(self):
        data_obj = self.env['ir.model.data']  # replace self.pool['ir.model.data']
        context = dict(self.env.context).copy()
        view = data_obj.xmlid_to_res_id(
            'l10n_vi_hr_timesheet.hr_attendance_confirmation_reason_form')
        context.update({
            'default_attendance_id': self.id,
            'default_type': 'agree',
        })
        return {
            'name': _('Agree'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.attendance.confirmation.reason',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'action': 'action_hr_attendance_confirmation_reason',
            'context': context,
        }

    @api.multi
    def action_degree(self):
        data_obj = self.env['ir.model.data']
        context = dict(self.env.context).copy()
        view = data_obj.xmlid_to_res_id(
            'l10n_vi_hr_timesheet.hr_attendance_confirmation_reason_form')
        context.update({
            'default_attendance_id': self.id,
            'default_type': 'degree',
        })
        return {
            'name': _('Degree'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.attendance.confirmation.reason',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'action': 'action_hr_attendance_confirmation_reason',
            'context': context,
        }

    def compute_cron_job(self):
        attendances = self.env['hr.attendance'].search([])
        for attendance in attendances:
            calendar_id = attendance.employee_id.resource_calendar_id
            if not calendar_id:
                raise osv.except_orm("Cảnh báo!",
                                     "Bạn chưa cấu hình lịch làm việc cho nhân viên " + str(attendance.employee_id.name))
            in_vals = {}
            out_vals = {}
            if attendance.check_in:
                in_vals = attendance.get_check_in(attendance.check_in, calendar_id)
            if attendance.check_out:
                out_vals = attendance.get_check_out(attendance.check_out, calendar_id)
            merge_vals = {**in_vals, **out_vals}
            if 'state' in in_vals.keys() and 'state' in out_vals.keys():
                merge_vals['state'] = 'late_and_early'
                merge_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' not in in_vals.keys() and 'state' not in out_vals.keys():
                if attendance.check_out:
                    merge_vals['state'] = 'done'
                    merge_vals['result_timekeeping'] = 'done'
                    merge_vals['number_min_late'] = 0
                    merge_vals['number_min_early'] = 0
                else:
                    merge_vals['state'] = 'miss_out'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['number_min_late'] = 0
                    merge_vals['number_min_early'] = 0
            elif 'state' in in_vals.keys() and 'state' not in out_vals.keys():
                if not attendance.check_out:
                    merge_vals['state'] = 'miss_out'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['hour_out'] = 0
                    merge_vals['number_min_early'] = 0
                else:
                    merge_vals['number_min_early'] = 0
                    merge_vals['result_timekeeping'] = 'yet_approved'
            elif 'state' in out_vals.keys() and 'state' not in in_vals.keys():
                if not attendance.check_in:
                    merge_vals['state'] = 'miss_in'
                    merge_vals['result_timekeeping'] = 'yet_approved'
                    merge_vals['hour_in'] = 0
                    merge_vals['number_min_late'] = 0
                else:
                    merge_vals['number_min_late'] = 0
                    merge_vals['result_timekeeping'] = 'yet_approved'
            if 'result_timekeeping' not in merge_vals.keys():
                merge_vals['result_timekeeping'] = 'yet_approved'
            attendance.write(merge_vals)