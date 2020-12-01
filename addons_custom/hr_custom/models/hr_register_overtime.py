from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError, except_orm, Warning, ValidationError
from odoo.osv import osv


class Hr_Register_overtime(models.Model):
    _name = 'hr.register.overtime'
    _description = "Register Overtime"
    _rec_name = 'employee_id'

    def _default_employee_id(self):
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee_id:
            raise ValidationError('Bạn chưa gắn tài khoản người dùng vào nhân viên.Vui lòng liên hệ bộ phận nhân sự để giải quyết')
        return employee_id.id

    employee_id = fields.Many2one('hr.employee', string='Employee', default=_default_employee_id)
    date = fields.Date(string='Date')
    hour_from = fields.Date(string='Hour From')
    hour_to = fields.Date(string='Hour To')
    state = fields.Selection([('draft', 'Draft'), ('approve', 'Approve')], string='State', default='draft')
    description = fields.Text('Description')

    @api.multi
    def register_draft(self):
        self.state = 'draft'

    @api.multi
    def register_approve(self):
        self.state = 'approve'

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise except_orm("Không thể xóa khác trạng thái Dự thảo")
        return super(Hr_Register_overtime, self).unlink()
