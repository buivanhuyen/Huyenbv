# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions
import datetime
from odoo.osv import osv
import pytz


class HrShift(models.Model):
    _name = 'hr.shift'
    _rec_name = 'name'
    _description = 'Shift Define'

    name = fields.Char('Name')
    hour_from = fields.Float(string='Hour From')
    hour_to = fields.Float(string='Hour To')
    description = fields.Char(string='Description')


class HrShiftManagement(models.Model):
    _name = 'hr.shift.work.management'
    _rec_name = 'name'
    _description = 'Shift Work Management'

    name = fields.Char(string="Name", default=lambda d: "Bảng phân ca tuần " + str(
        datetime.datetime.now().date().strftime("%V")) + " tháng " + str(datetime.datetime.now().month) + " năm " + str(
        datetime.datetime.now().year))
    date_from = fields.Date(string="Date From", default=lambda d: datetime.datetime.now().date())
    date_to = fields.Date(string="Date To",
                          default=lambda d: (datetime.datetime.now() + datetime.timedelta(days=7)).date())
    department_ids = fields.Many2many('hr.department', string="Departments")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    lines = fields.One2many('hr.shift.employee', 'shift_management_id', string="Shift Employee")
    description = fields.Text(string="Description")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise exceptions.ValidationError(
                    "Không thể xóa bản ghi khi đã xác nhận. Vui lòng kiểm tra lại. Xin cảm ơn")
        return super(HrShiftManagement, self).unlink()

    @api.onchange('department_ids')
    def onchange_department_ids(self):
        department_ids = self.department_ids.ids
        employee_ids = self.env['hr.employee'].search([('department_id', 'in', department_ids)])
        vals = []
        for emp in employee_ids:
            if self.date_from and self.date_to and self.date_to >= self.date_from:
                for i in range(0, (self.date_to - self.date_from).days + 1):
                    vals.append({
                        'employee_id': emp.id,
                        'date_from': self.date_from,
                        'date_to': self.date_to,
                        'date': self.date_from + datetime.timedelta(days=i)
                    })
        self.lines = vals

    @api.multi
    def action_approve(self):
        self.state = 'done'


class HrShiftEmployee(models.Model):
    _name = 'hr.shift.employee'
    _rec_name = 'employee_id'
    _description = 'Shift Employee'

    shift_management_id = fields.Many2one('hr.shift.work.management', ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    date = fields.Date(string="Date")
    datetime_from = fields.Datetime(string="Datetime From", compute="_compute_datetime", store=True)
    datetime_to = fields.Datetime(string="Datetime To", compute="_compute_datetime", store=True)
    shift_id = fields.Many2one('hr.shift', string="Shift")

    @api.onchange('employee_id')
    def onchange_employee(self):
        self.date_from = self.shift_management_id.date_from
        self.date_to = self.shift_management_id.date_to

    @api.onchange('shift_id')
    def onchange_shift(self):
        if self.shift_id.id and self.date:
            # todo timein
            time_in = self.shift_id.hour_from
            hour_in = int(time_in)
            # todo timeout
            time_out = self.shift_id.hour_to
            hour_out = int(time_out)
            if hour_in <= hour_out:
                date_from = datetime.date(self.date.year, self.date.month, self.date.day)
                date_to = datetime.date(self.date.year, self.date.month, self.date.day)
            else:
                date_from = datetime.date(self.date.year, self.date.month, self.date.day)
                date_to = datetime.date(self.date.year, self.date.month, self.date.day) + datetime.timedelta(days=1)
            self.date_from = date_from
            self.date_to = date_to
        else:
            self.date_from = datetime.datetime.now().date()
            self.date_to = datetime.datetime.now().date()

    def convert_date_to_utc(self, date):
        try:
            local = pytz.timezone(self.env.context.get('tz'))
        except:
            local = pytz.timezone(self._context.get('tz'))
        seconds = local._utcoffset.days * 24 * 3600 + local._utcoffset.seconds
        if local.zone.upper() == 'Asia/Ho_Chi_Minh'.upper():
            seconds = seconds - 7 * 60
        date = date - datetime.timedelta(seconds=seconds)
        date.strftime('%Y-%m-%d: %H:%M:%S')
        return date.replace(tzinfo=None)

    @api.one
    @api.depends('date', 'shift_id')
    def _compute_datetime(self):
        if self.shift_id.id and self.date:
            # todo timein
            time_in = self.shift_id.hour_from
            hour_in = int(time_in)
            min_in = int((time_in - hour_in) * 60)
            # todo timeout
            time_out = self.shift_id.hour_to
            hour_out = int(time_out)
            min_out = int((time_out - hour_out) * 60)
            if hour_in <= hour_out:
                datetime_from = datetime.datetime(self.date.year, self.date.month, self.date.day, hour_in, min_in,
                                                  0)
                datetime_to = datetime.datetime(self.date.year, self.date.month, self.date.day, hour_out, min_out,
                                                0)
            else:
                datetime_from = datetime.datetime(self.date.year, self.date.month, self.date.day, hour_in, min_in,
                                                  0)
                datetime_to = datetime.datetime(self.date.year, self.date.month, self.date.day, hour_out, min_out,
                                                0) + datetime.timedelta(days=1)
            self.datetime_from = self.convert_date_to_utc(datetime_from)
            self.datetime_to = self.convert_date_to_utc(datetime_to)


class HrShiftEmployeeChange(models.Model):
    _name = 'hr.shift.employee.change'
    _description = 'Shift Employee Change'
    _rec_name = 'employee_id'

    shift_old_id = fields.Many2one('hr.shift', string="Shift Old", ondelete="restrict")
    shift_new_id = fields.Many2one('hr.shift', string="Shift New", ondelete="restrict")
    shift_management_id = fields.Many2one('hr.shift.work.management', ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string="Employee", ondelete="restrict")
    date = fields.Date(string="Date")
    reason = fields.Char(string="Reason")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft', string="State")

    @api.onchange('shift_management_id')
    def onchange_shift_management_id(self):
        if self.shift_management_id.id:
            shift_emps = self.env['hr.shift.employee'].search(
                [('shift_management_id', '=', self.shift_management_id.id)])
            employee_ids = [ep.employee_id.id for ep in shift_emps]
            return {
                'domain': {
                    'employee_id': [('id', 'in', employee_ids)]
                }
            }

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        if self.employee_id.id:
            shift_emps = self.env['hr.shift.employee'].search(
                [('shift_management_id', '=', self.shift_management_id.id), ('employee_id', '=', self.employee_id.id)])
            shift_ids = [ep.shift_id.id for ep in shift_emps]
            return {
                'domain': {
                    'shift_old_id': [('id', 'in', shift_ids)]
                }
            }

    @api.onchange('date')
    def onchange_date(self):
        if self.employee_id.id and self.date and self.shift_management_id.id:
            shift_emps = self.env['hr.shift.employee'].search(
                [('date', '=', self.date), ('shift_management_id', '=', self.shift_management_id.id),
                 ('employee_id', '=', self.employee_id.id)])
            shift_ids = [ep.shift_id.id for ep in shift_emps]
            self.shift_old_id = shift_ids[0]
            return {
                'domain': {
                    'shift_old_id': [('id', 'in', shift_ids)]
                }
            }

    @api.multi
    def action_approve(self):
        shift_emps = self.env['hr.shift.employee'].search(
            [('date', '=', self.date), ('shift_management_id', '=', self.shift_management_id.id),
             ('employee_id', '=', self.employee_id.id), ('shift_id', '=', self.shift_old_id.id)], limit=1)
        if not shift_emps.id:
            raise exceptions.AccessError("Không tồn tại phân ca cho nhân viên. Vui lòng kiểm tra lại.")
        shift_emps.write({
            'shift_id': self.shift_new_id.id
        })
        shift_emps.onchange_shift()

        self.write({
            'state': 'done'
        })
