# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import except_orm
from odoo.osv import osv
import base64
import xlrd
import threading

try:
    import cStringIO as stringIOModule
except ImportError:
    try:
        import StringIO as stringIOModule
    except ImportError:
        import io as stringIOModule

import xlrd
import xlwt
from datetime import datetime, timedelta

weekday = {'0': 'Monday',
           '1': 'Tuesday',
           '2': 'Wednesday',
           '3': 'Thursday',
           '4': 'Friday',
           '5': 'Saturday',
           '6': 'Sunday'}


# Cau hinh ti le lam them gio
class HrTimesheetOvertimeConfig(models.Model):
    _name = 'hr.timesheet.overtime.config'

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive')], default="draft")
    percent_night = fields.Float(string="Percent Night")
    percent_weekend = fields.Float(string="Percent Weekend")
    percent_holiday = fields.Float(string="Percent Holiday")
    department_ids = fields.Many2many('hr.department', 'hr_timesheet_overtime_department_rel', 'config_id',
                                      'department_id', string="Apply on Departments")
    employee_ids = fields.Many2many('hr.employee', 'hr_timesheet_overtime_employee_rel', 'config_id', 'employee_id',
                                    string="Not apply for employees")
    number_of_hours = fields.Float(string="Number of Hours",
                                   help="The number of hours start to be paid overtime. Example: "
                                        "According to theory, 17h you must check out and do something. However, you will have to work overtime today. "
                                        "If Number of Hours equal 1 and 17h50m you checkout, you won't added overtime. ")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrTimesheetOvertimeConfig, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False


# Cau hinh muc phat di muon
class HrTimesheetBreakLateConfig(models.Model):
    _name = 'hr.timesheet.break.config'

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive')], default="draft")

    type = fields.Selection([('late', 'Late')], default='late')
    appearance = fields.Selection(
        [('total', 'Total of Minutes'), ('count', 'Total of Count'), ('code', 'By Code for Everyday')], default='total',
        help="Total of Minutes: A minute employee receive 1000. If Multiplier = 10 and employee was minutes late 6 minutes. So, total = 10*1000*6.  \n"
             "Total of Count: If amount = 100k and employee was late 6 times. So, total = 6 * 100000. \n"
             "By Code for Everyday: None")
    amount = fields.Float(string="Amount")  # Ap dung cho moi lan di muon/ve som = bao nhieu tien
    multiplier = fields.Float(
        string="Multiplier")  # Ap dung cho tong so phut. 1p nhan vien duoc 1k, Neu multiplier = 10 va nhan vien di muon 6p. Vay tong tien phat = 10 * 6 * 1000

    lines = fields.One2many('hr.timesheet.break.config.line', 'config_id',
                            string="Details Breaking")  # Ap dung cho theo ma boi hang ngay

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrTimesheetBreakLateConfig, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False


class HrTimesheetBreaConfigLine(models.Model):
    _name = 'hr.timesheet.break.config.line'

    config_id = fields.Many2one('hr.timesheet.break.config')
    code = fields.Char(string="Code")
    minutes = fields.Float(string="Minutes")
    appearance = fields.Selection(
        [('money', 'Money'), ('work', 'Work day')], default='money')
    value = fields.Float(string="Value")
    note = fields.Text(string="Note")


class HrTimesheetBreakEarlyConfig(models.Model):
    _inherit = 'hr.timesheet.break.config'

    type = fields.Selection([('late', 'Late'), ('early', 'Early')], default='late')


