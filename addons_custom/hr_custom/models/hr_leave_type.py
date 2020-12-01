from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError, except_orm, Warning, ValidationError
from odoo.osv import osv


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    x_type = fields.Selection(
        [('1', 'Allow Leaves'), ('2', 'Holidays'), ('3', 'Policy Leaves'), ('4', 'Sick Leaves'), ('5', 'Maternity'),
         ('6', 'Unpaid Leaves'), ('7', 'Unreasonal Leaves'), ('0', 'Other')], string="Type Leaves", default='0')

class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    def _default_employee_id(self):
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee_id:
            raise ValidationError('Bạn chưa gắn tài khoản người dùng vào nhân viên.Vui lòng liên hệ bộ phận nhân sự để giải quyết')
        return employee_id.id

    employee_id = fields.Many2one('hr.employee', string='Employee', default=_default_employee_id)