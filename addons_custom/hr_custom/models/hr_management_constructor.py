from datetime import datetime
from odoo.exceptions import ValidationError
from odoo import models, fields, api
from odoo.osv import osv
from datetime import datetime, timedelta, date as t_date
import calendar
import collections

class Management_Constructor(models.Model):
    _name = 'hr.management.constructor'

    name = fields.Char(string='Name', default=lambda d: "Đi công trình %s - %s " % (
        datetime.now().date().month, datetime.now().date().year))
    date_from = fields.Date(string='Date From', default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month, 1))
    date_to = fields.Date(string='Date To', default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month,
                                                   calendar.monthrange(datetime.now().date().year,
                                                                       datetime.now().date().month)[1]))
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm')], string='State', default='draft')
    management_constructor_ids = fields.One2many('hr.management.constructor.employee', 'management_constructor_id')

    @api.multi
    def validate_management_constructor_confirm(self):
        # Kiểm tra xem có 2 nhân viên trùng nhau
        query = """
                SELECT employee_id, count(employee_id)
                FROM hr_management_constructor_employee
                WHERE management_constructor_id = %s
                GROUP BY (employee_id)
                HAVING COUNT(*) > 1
                """
        self._cr.execute(query, ([self.id]))
        res = self._cr.dictfetchall()
        for detail in res:
            emp_id = self.env['hr.employee'].search([('id', '=', detail['employee_id'])])
            if detail['count'] > 1:
                raise ValidationError('Nhân viên %s đang có nhiều hơn 1 dòng.Vui lòng kiểm tra lại' % emp_id.name)

        constructor_ids = self.env['hr.management.constructor'].search(
            [('date_from', '>=', self.date_from), ('date_to', '<=', self.date_to), ('state', '=', 'confirm')])

        if len(constructor_ids) >= 1:
            raise ValidationError(
                'Bạn đang có %s bảng quản lý đi công trình trong cùng 1 tháng.Vui lòng kiểm tra lại!' % len(
                    constructor_ids))
        self.state = 'confirm'

    @api.multi
    def validate_management_constructor_draft(self):
        self.state = 'draft'

    @api.multi
    def unlink(self):
        if self.state == 'draft':
            raise ValidationError('Can\'t delete!')
            # raise ValidationError("Can't delete this order")
        return super(Management_Constructor, self).unlink()

    @api.multi
    def action_caculate(self):
        self.management_constructor_ids = None
        query = """
                    SELECT employee_id, date_from, date_to, count(employee_id)
                    FROM hr_constructor
                    WHERE date_from >= %s AND date_to<= %s
                    GROUP BY (employee_id, date_from, date_to)
                """
        self._cr.execute(query, ([self.date_from, self.date_to]))
        res = self._cr.dictfetchall()
        lines = []
        for line in res:
            number_constructor = line['date_to'] - line['date_from']
            number_constructor_day = number_constructor.days + 1
            val = {
                'employee_id': line['employee_id'],
                'number_constructor': number_constructor_day
            }
            if val['employee_id'] not in lines:
                lines.append(val)



        self.management_constructor_ids = lines
        pass

class Management_Constructor_Employee(models.Model):
    _name = 'hr.management.constructor.employee'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee')
    number_constructor = fields.Float(string='Number Constructor')
    management_constructor_id = fields.Many2one('hr.management.constructor')


