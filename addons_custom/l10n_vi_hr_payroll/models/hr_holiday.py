# -*- coding: utf-8 -*-
import logging
import math
from datetime import timedelta, datetime

from odoo import api, fields, models
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools import float_compare
from odoo.tools.translate import _
import threading
from odoo.osv import osv


class HrHoliday(models.Model):
    _inherit = 'hr.holidays'

    holiday_type = fields.Selection([
        ('employee', 'By Employee'),
        ('category', 'By Employee Tag'),
        ('department', 'By Department')
    ], string='Allocation Mode', readonly=True, required=True, default='employee',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]},
        help='By Employee: Allocation/Request for individual Employee, By Employee Tag: Allocation/Request for group of employees in category,'
             'By Department: Allocation/Request for all employee in department.')
    department_ids = fields.Many2many('hr.department', 'hr_holidays_department_rel', 'holiday_id', 'department_id',
                                      string="Departments")
    date_f = fields.Date(string="Date From", compute='_compute_worked_date', store=True, readonly=True)
    date_t = fields.Date(string="Date To", compute='_compute_worked_date', store=True, readonly=True)
    # manager_id = fields.Many2one('hr.employee', string="Manager")
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
    ], string='Status', readonly=True, track_visibility='onchange', copy=False, default='draft',
        help="The status is set to 'To Submit', when a leave request is created." +
             "\nThe status is 'To Approve', when leave request is confirmed by user." +
             "\nThe status is 'Refused', when leave request is refused by manager." +
             "\nThe status is 'Approved', when leave request is approved by manager.")

    _sql_constraints = [
        ('type_value',
         "unique(create_date)",
         "The employee or employee category of this request is missing. Please make sure that your user login is linked to an employee."),
        ('date_check2', "CHECK ( (type='add') OR (date_from <= date_to))",
         "The start date must be anterior to the end date."),
        ('date_check', "CHECK ( number_of_days_temp >= 0 )", "The number of days must be greater than 0."),
    ]

    @api.depends('date_from', 'date_to')
    def _compute_worked_date(self):
        print("Hello World")
        for holiday in self:
            if holiday.date_to:
                date_out = datetime.strptime(holiday.date_to, '%Y-%m-%d %H:%M:%S')
                date_out = date_out + timedelta(hours=7)
                holiday.date_t = date_out.date()
            if holiday.date_from:
                date_in = datetime.strptime(holiday.date_from, '%Y-%m-%d %H:%M:%S')
                date_in = date_in + timedelta(hours=7)
                holiday.date_f = date_in.date()

    @api.multi
    def action_validate(self):
        self._check_security_action_validate()

        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        for holiday in self:
            if holiday.state not in ['confirm', 'validate1']:
                raise UserError(_('Leave request must be confirmed in order to approve it.'))
            if holiday.state == 'validate1' and not holiday.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                raise UserError(_('Only an HR Manager can apply the second approval on leave requests.'))

            holiday.write({'state': 'validate'})
            if holiday.double_validation:
                holiday.write({'second_approver_id': current_employee.id})
            else:
                holiday.write({'first_approver_id': current_employee.id})
            if holiday.holiday_type == 'employee' and holiday.type == 'remove':
                holiday._validate_leave_request()
            elif holiday.holiday_type == 'category':
                leaves = self.env['hr.holidays']
                for employee in holiday.category_id.employee_ids:
                    values = holiday._prepare_create_by_category(employee)
                    leaves += self.with_context(mail_notify_force_send=False).create(values)
                # TODO is it necessary to interleave the calls?
                leaves.action_approve()
                if leaves and leaves[0].double_validation:
                    leaves.action_validate()
            elif holiday.holiday_type == 'department':
                employees = self.env['hr.employee'].search([('department_id', 'in', holiday.department_ids.ids)])
                leaves = self.env['hr.holidays']
                for employee in employees:
                    values = holiday._prepare_create_by_category(employee)
                    leaves += self.with_context(mail_notify_force_send=False).create(values)
                # TODO is it necessary to interleave the calls?
                leaves.action_approve()
                if leaves and leaves[0].double_validation:
                    leaves.action_validate()
        return True

    @api.multi
    def action_confirm(self):
        if self.type == 'remove':
            if self.manager_id.id:
                email = self.manager_id.work_email
                if self.manager_id.user_id.id:
                    partner_id = self.manager_id.user_id.partner_id
                else:
                    partner_id = self.manager_id.address_home_id
                if not partner_id:
                    raise osv.except_orm("Cảnh báo!",
                                         "Vui lòng báo lại quản trị viên cấu hình Đối tác (Private Address) trong Thông tin Liên hệ của Nhân viên " + str(
                                             self.manager_id.name) + ". Xin cảm ơn.")
                if email:
                    mail = self.env['izi.sent.mail.template'].create({
                        'name': '[NESTA] V/v xin nghỉ phép của nhân viên ' + str(self.employee_id.name) + ' từ ' + str(
                            self.date_from) + ' đến ' + str(self.date_to),
                        'model': 'hr.holidays',
                        'res_id': self.id,
                        'partner_id': partner_id.id,
                        'content': 'ĐỀ NGHỊ XIN NGHỈ PHÉP',
                        'content_before': 'Nhân viên ' + str(self.employee_id.name),
                        'content_after': '. Để xem chi tiết và phê duyệt đơn xin nghỉ, bạn vui lòng click chọn vào button dưới đây. Xin cảm ơn.'
                    })
                    thread_var = threading.Thread(target=mail.action_send_mail_major(True, True))
                    thread_var.start()
        return super(HrHoliday, self).action_confirm()

    @api.multi
    def action_refuse(self):
        res = super(HrHoliday, self).action_refuse()
        if self.type == 'remove':
            if self.manager_id.id:
                email = self.employee_id.work_email
                if self.manager_id.user_id.id:
                    partner_id = self.manager_id.user_id.partner_id
                else:
                    partner_id = self.manager_id.address_home_id
                if not partner_id:
                    raise osv.except_orm("Cảnh báo!",
                                         "Vui lòng báo lại quản trị viên cấu hình Đối tác (Private Address) trong Thông tin Liên hệ của Nhân viên " + str(
                                             self.employee_id.name) + ". Xin cảm ơn.")
                if email:
                    mail = self.env['izi.sent.mail.template'].create({
                        'name': '[NESTA] V/v xin nghỉ phép của NV ' + str(
                            self.employee_id.name) + ' KHÔNG ĐƯỢC CHẤP THUẬN',
                        'model': 'hr.holidays',
                        'res_id': self.id,
                        'partner_id': partner_id.id,
                        'content': 'KHÔNG ĐỒNG Ý CHO NGHỈ PHÉP',
                        'content_before': 'Quản lý ' + str(self.manager_id.name) + ': ',
                        'content_after': '. Để xem chi tiết, bạn vui lòng click chọn vào button dưới đây. Xin cảm ơn.'
                    })
                    thread_var = threading.Thread(target=mail.action_send_mail_major(True, True))
                    thread_var.start()
        return res
