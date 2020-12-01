from odoo import models, fields, api
from odoo.exceptions import except_orm


class Hr_Management_Lunch(models.Model):
    _name = 'hr.management.lunch'
    _description = "Management Lunch"

    name = fields.Char(string='Management Lunch')
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm')], string='State', default='draft')
    lunch_ids = fields.One2many('hr.management.lunch.employee', 'lunch_id', string="Lunch Employee")

    @api.multi
    def draft(self):
        self.state = 'draft'

    @api.multi
    def confirm(self):
        self.state = 'confirm'

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise except_orm("Không thể xóa khác trạng thái Dự thảo")
        return super(Hr_Management_Lunch, self).unlink()


class Hr_Management_Lunch_Employee(models.Model):
    _name = 'hr.management.lunch.employee'

    employee_id = fields.Many2one('hr.employee')
    number_lunch = fields.Float(string='Number Lunch')
    lunch_id = fields.Many2one('hr.management.lunch', ondelete="cascade")
