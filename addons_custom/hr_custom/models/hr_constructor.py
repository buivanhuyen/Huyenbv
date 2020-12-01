from datetime import datetime
from odoo.exceptions import ValidationError
from odoo import models, fields, api
from odoo.osv import osv


class Constructor(models.Model):
    _name = 'hr.constructor'
    _rec_name = 'employee_id'

    def _default_employee_id(self):
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee_id:
            raise ValidationError('Bạn chưa gắn tài khoản người dùng vào nhân viên.Vui lòng liên hệ bộ phận nhân sự để giải quyết')
        return employee_id.id

    date_from = fields.Date(string='Date From',default=lambda self: fields.Date.today())
    date_to = fields.Date(string='Date To')
    employee_id = fields.Many2one('hr.employee', string='Employee', default=_default_employee_id)
    description = fields.Char(string='Description')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm')], string='State', default='draft')


    @api.multi
    def validate_management_constructor_confirm(self):
        if self.date_to < self.date_from:
            raise ValidationError('Ngày kết thúc không thể nhỏ hơn ngày bắt đầu')
        if self.date_to.month != self.date_from.month:
            raise ValidationError('Đi công tác chỉ có tác dụng trong cùng 1 tháng!')
        self.state = 'confirm'

    @api.multi
    def validate_management_constructor_draft(self):
        self.state = 'draft'

    @api.multi
    def unlink(self):
        if self.state == 'draft':
            raise ValidationError('Can\'t delete!')
            # raise ValidationError("Can't delete this order")
        return super(Constructor, self).unlink()


