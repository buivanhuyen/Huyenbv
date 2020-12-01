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
from odoo.exceptions import UserError, except_orm, ValidationError

class HrTimeSheetLateEarly(models.Model):
    _name = 'hr.timesheet.late.early'
    _rec_name = 'employee_id'

    def _default_employee_id(self):
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee_id:
            raise ValidationError('Bạn chưa gắn tài khoản người dùng vào nhân viên.Vui lòng liên hệ bộ phận nhân sự để giải quyết')
        return employee_id.id

    employee_id = fields.Many2one('hr.employee', string='Employee', default=_default_employee_id)
    date = fields.Date(string='Date', default=lambda self: fields.Date.today())
    type = fields.Selection([('late', 'Late'), ('early', 'Early')], 'Type', default='late')
    state = fields.Selection([('draft', 'Draft'), ('validate1', 'Validate 1'), ('validate', 'Validate')], default='draft')
    description = fields.Char('Description')

    @api.multi
    def action_validate1(self):
        for line in self:
            line.state = 'validate1'

    @api.multi
    def action_validate(self):
        for line in self:
            line.state = 'validate'

    @api.multi
    def unlink(self):
        for line in self:
            if line.state != 'draft':
                raise ValidationError('Bạn chỉ có thể xóa bản ghi ở trạng thái bản thảo.')
        return super(HrTimeSheetLateEarly, self).unlink()