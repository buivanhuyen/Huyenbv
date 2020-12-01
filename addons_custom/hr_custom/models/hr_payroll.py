# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, exceptions
from odoo.osv import osv
import base64
import xlrd
import threading
from odoo.exceptions import UserError, except_orm
from itertools import groupby



try:
    import cStringIO as stringIOModule
except ImportError:
    try:
        import StringIO as stringIOModule
    except ImportError:
        import io as stringIOModule

import xlrd
import xlwt
from datetime import datetime, timedelta, date as t_date
from odoo.exceptions import except_orm, ValidationError
import calendar

weekday = {'0': 'Monday',
           '1': 'Tuesday',
           '2': 'Wednesday',
           '3': 'Thursday',
           '4': 'Friday',
           '5': 'Saturday',
           '6': 'Sunday'}


class HrPayroll(models.Model):
    _name = "hr.payroll"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll'

    name = fields.Char(string="Name", default=lambda d: "%s - %s " % (
        datetime.now().date().month, datetime.now().date().year))
    date_from = fields.Date(string="From Date",
                            default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month, 1))
    date_to = fields.Date(string="To Date",
                          default=lambda d: t_date(datetime.now().date().year, datetime.now().date().month,
                                                   calendar.monthrange(datetime.now().date().year,
                                                                       datetime.now().date().month)[1]))
    department_ids = fields.Many2many('hr.department', 'hr_payroll_hr_department_rel', 'department_id', 'payroll_id',
                                      string="Departments")
    state = fields.Selection(
        [('draft', 'Draft'), ('cal', 'Calculate'), ('wait', 'Wait Approve'), ('approved', 'Approved')], default='draft',
        string="State")
    lines = fields.One2many('hr.payroll.line', 'payroll_id', string="Payroll")
    lines_ids = fields.One2many('hr.payroll.line', 'payroll_id', string="Payroll")
    upload_file = fields.Binary(string='File Upload')
    file_name = fields.Char(string='File Name')
    count_payslip = fields.Integer(string="Count Payslip", compute="_compute_count_payslip")
    payslip_ids = fields.One2many('hr.payslip', 'payroll_id', string="Payslips")
    timesheet_id = fields.Many2one('hr.timesheet', string="Timesheet")

    def _compute_count_payslip(self):
        for record in self:
            record.count_payslip = len(record.payslip_ids)

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise exceptions.ValidationError(
                    "Không thể xóa bản ghi khi đã xác nhận. Vui lòng kiểm tra lại. Xin cảm ơn")
        return super(HrPayroll, self).unlink()

    @api.multi
    def get_employee(self):
        self.lines.unlink()
        department_ids = self.department_ids.ids
        employee_ids = self.env['hr.employee'].search([('department_id', 'in', department_ids), ('active', '=', True)])
        vals = []
        for emp in employee_ids:
            if self.date_from and self.date_to and self.date_to >= self.date_from:
                contract = self.env['hr.contract'].sudo().search(
                    [('state', 'in', ['open', 'pending']), ('employee_id', '=', emp.id)])
                val = {
                    'employee_id': emp.id,
                    'department_id': emp.department_id.id,
                    'open_date': emp.x_start_date,
                }
                if len(contract) == 1:
                    val.update(contract_id=contract.id)
                # tim kiem cham cong
                timesheet_line_id = self.env['hr.timesheet.line'].search(
                    [('employee_id', '=', emp.id), ('timesheet_id.date_from', '<=', self.date_from),
                     ('timesheet_id.date_to', '<=', self.date_to)])
                if len(timesheet_line_id) == 1:
                    val.update(timesheet_line_id=timesheet_line_id.id)
                    vals.append(val)

        self.lines = vals

    @api.multi
    def action_calculate(self):
        for payroll_line in self.lines:
            employee = payroll_line.employee_id
            contract = payroll_line.contract_id
            timsheet_employee = payroll_line.timesheet_line_id
            if not timsheet_employee:
                raise exceptions.ValidationError(
                    _("Vui lòng lựa chọn bảng công để tính lương cho %s " % (employee.name)))
            if not contract:
                raise exceptions.ValidationError(
                    _("Vui lòng lựa chọn hợp đồng để tính lương cho %s " % (employee.name)))
            standard_workday = timsheet_employee.standard_workday
            real_workday = timsheet_employee.real_workday or 1
            ratio = real_workday / (standard_workday or 1)
            # ho tro di cong trinh
            support_constructor = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_support_constructor', 'False')
            try:
                support_constructor = float(support_constructor)
            except:
                support_constructor = 50000
             # mức tính lam thêm giờ
            over_time = self.env['hr.timesheet.overtime.config'].search([('state', '=', 'active')], limit=1)
            if not over_time:
                raise ValidationError('Bạn chưa cấu hình làm thêm giờ.Vui lòng kiểm tra lại')

            try:
                overtime_weekdays = float(over_time.percent_night)
            except:
                overtime_weekdays = 1

            try:
                overtime_weekend = float(over_time.percent_weekend)
            except:
                overtime_weekend = 1.5

            try:
                overtime_holiday = float(over_time.percent_holiday)
            except:
                overtime_holiday = 3

            try:
                overtime_shift_night = float(overtime_shift_night)
            except:
                overtime_shift_night = 30
            # mức tính giảm trừ thuế tncn

            ded_overtime_weekdays = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_ded_overtime_weekdays', 'False')
            ded_overtime_weekend = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_ded_overtime_weekend', 'False')
            ded_overtime_holiday = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_ded_overtime_holiday', 'False')
            try:
                ded_overtime_weekdays = float(ded_overtime_weekdays)
            except:
                ded_overtime_weekdays = 50

            try:
                ded_overtime_weekend = float(ded_overtime_weekend)
            except:
                ded_overtime_weekend = 100

            try:
                ded_overtime_holiday = float(ded_overtime_holiday)
            except:
                ded_overtime_holiday = 0
            # tính thuế tncn
            limit_tax_personal = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_limit_tax_personal', 'False')
            limit_dependant = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_limit_dependant', 'False')

            try:
                limit_tax_personal = float(limit_tax_personal)
            except:
                limit_tax_personal = 9000000

            try:
                limit_dependant = float(limit_dependant)
            except:
                limit_dependant = 3600000

            # ăn trưa
            price_lunch = self.env['ir.config_parameter'].sudo().get_param(
                'parameter_lunch', 'False')

            try:
                price_lunch = float(price_lunch)
            except:
                price_lunch = 10000

            # vals
            vals = {}
            # luong co ban va tro cap
            basic_contract = contract.wage  # Lương
            allowance_fix_contract = contract.x_allowance_fix   #PC cố định
            allowance_special_contract = contract.x_allowance_technique   #Phụ cấp chuyên môn
            allowance_responsible_contract = contract.x_allowance_responsibility #phụ cấp trách nhiệm
            allowance_oil_contract = contract.x_allowance_travel     #Phụ cấp đi lại
            allowance_phone_contract = contract.x_allowance_telephone # Phụ cấp điện thoại
            allowance_diligence_contract = contract.x_allowance_diligence #Phụ cấp chuyên cần
            allowance_house_contract = contract.x_allowance_dwelling_house # Phụ cấp nhà ở
            allowance_other_contract = contract.x_allowance_other # Phụ cấp khác
            total_contract = basic_contract + allowance_oil_contract + allowance_other_contract + \
                             allowance_phone_contract + allowance_diligence_contract + allowance_fix_contract \
                             + allowance_special_contract + allowance_responsible_contract + allowance_house_contract
            #  A. Lương và phụ cấp trên Hợp đồng
            vals.update(
                basic_contract=contract.wage,
                allowance_fix_contract=contract.x_allowance_fix,
                allowance_special_contract=contract.x_allowance_technique,
                allowance_responsible_contract=contract.x_allowance_responsibility,
                allowance_oil_contract=contract.x_allowance_travel,
                allowance_phone_contract=contract.x_allowance_telephone,
                allowance_diligence_contract=contract.x_allowance_diligence,
                allowance_house_contract=contract.x_allowance_dwelling_house,
                allowance_other_contract=contract.x_allowance_other,
            )
            # C.Lương cơ bản và các phụ cấp thực tế
            basic_real = contract.wage * ratio
            holiday_pay = total_contract * (timsheet_employee.number_allow_leave + timsheet_employee.number_holiday_leave)/ standard_workday
            allowance_fix_real = contract.x_allowance_fix * ratio  # co dinh
            allowance_special_real = contract.x_allowance_technique * ratio  # chuyên môn
            allowance_responsible_real = contract.x_allowance_responsibility * ratio  # trách nhiệm
            allowance_oil_real = contract.x_allowance_travel * ratio  # xăng xe, đi lại
            allowance_phone_real = contract.x_allowance_telephone * ratio  # điện thoại
            allowance_diligence_real = contract.x_allowance_diligence * ratio  # chuyên cần
            allowance_house_real = contract.x_allowance_dwelling_house * ratio  # nhà ở
            allowance_other_real = contract.x_allowance_other * ratio  # khác
            allowance_constructor_real = timsheet_employee.number_constructor * support_constructor
            vals.update(
                basic_real=basic_real,
                holiday_pay=holiday_pay,
                allowance_fix_real=allowance_fix_real,
                allowance_special_real=allowance_special_real,
                allowance_responsible_real=allowance_responsible_real,
                allowance_oil_real=allowance_oil_real,
                allowance_phone_real=allowance_phone_real,
                allowance_diligence_real=allowance_diligence_real,
                allowance_house_real=allowance_house_real,
                allowance_other_real=allowance_other_real,
                allowance_constructor_real=allowance_constructor_real,
            )
            # E.Lương làm việc tăng ca, PC đêm
            total_salary_cal_overtime = basic_contract + allowance_special_contract + allowance_responsible_contract  # LCB + PC chuyên môn + PC trách nhiệm
            overtime_weekday_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_weekdays * overtime_weekdays / standard_workday
            overtime_weekend_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_weekend * overtime_weekend / standard_workday
            overtime_holiday_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_holidays * overtime_holiday / standard_workday
            allowance_shift_night = total_salary_cal_overtime * timsheet_employee.hour_overtime_shift3 * overtime_shift_night / standard_workday
            vals.update(
                overtime_weekday_salary=overtime_weekday_salary,
                overtime_weekend_salary=overtime_weekend_salary,
                overtime_holiday_salary=overtime_holiday_salary,
                allowance_shift_night=allowance_shift_night,
            )
            # Tổng thu nhập miễn thuế trong tháng
            sickness_by_social = payroll_line.pay_for_social_insurance
            salary_overtime_night = contract.wage * ded_overtime_weekend * timsheet_employee.hour_overtime_weekend / real_workday / 8 / 100 + \
                                    contract.wage * ded_overtime_weekdays * timsheet_employee.hour_overtime_weekdays / real_workday / 8 / 100 \
                                    + contract.wage * ded_overtime_holiday * timsheet_employee.hour_overtime_holidays / 8 / 100 \
                                    + allowance_shift_night

            allowance_phone = allowance_phone_real
            vals.update(
                sickness_by_social=sickness_by_social,
                salary_overtime_night=salary_overtime_night,
                allowance_phone=allowance_phone,
            )
            # F.Đóng BHXH
            vals.update(
                level_insurance=contract.x_salary
            )
            # G.Thuế thu nhập cá nhân
            allowances_family = limit_tax_personal + limit_dependant * payroll_line.number_person_dependant
            vals.update(
                allowances_family=allowances_family
            )
            # H.Các khoản khấu trừ khác
            total_lunch = timsheet_employee.number_lunch * price_lunch
            vals.update(
                total_lunch=total_lunch
            )

            # Đi muộn về sớm
            late_early = self.env['hr.timesheet.break.config'].search([('state', '=', 'active')],limit=1)
            vals.update(
                total_mulct= timsheet_employee.late_early * late_early.amount
            )
            payroll_line.write(vals)
        self.write({
            'state': 'cal'
        })
    #
    # @api.multi
    # def action_recalculate(self):
    #     for payroll_line in self.lines:
    #         employee = payroll_line.employee_id
    #         contract = payroll_line.contract_id
    #         timsheet_employee = payroll_line.timesheet_line_id
    #         standard_workday = timsheet_employee.standard_workday
    #         real_workday = timsheet_employee.real_workday or 1
    #         ratio = real_workday / (standard_workday or 1)
    #         # ho tro di cong trinh
    #         support_constructor = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_support_constructor', 'False')
    #         try:
    #             support_constructor = float(support_constructor)
    #         except:
    #             support_constructor = 50000
    #         # mức tính lam thêm giờ
    #         overtime_weekdays = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_overtime_weekdays', 'False')
    #         overtime_weekend = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_overtime_weekend', 'False')
    #         overtime_holiday = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_overtime_holiday', 'False')
    #         overtime_shift_night = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_overtime_shift_night', 'False')
    #         try:
    #             overtime_weekdays = float(overtime_weekdays)
    #         except:
    #             overtime_weekdays = 150
    #
    #         try:
    #             overtime_weekend = float(overtime_weekend)
    #         except:
    #             overtime_weekend = 200
    #
    #         try:
    #             overtime_holiday = float(overtime_holiday)
    #         except:
    #             overtime_holiday = 300
    #
    #         try:
    #             overtime_shift_night = float(overtime_shift_night)
    #         except:
    #             overtime_shift_night = 30
    #         # mức tính giảm trừ thuế tncn
    #         ded_overtime_weekdays = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_ded_overtime_weekdays', 'False')
    #         ded_overtime_weekend = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_ded_overtime_weekend', 'False')
    #         ded_overtime_holiday = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_ded_overtime_holiday', 'False')
    #         try:
    #             ded_overtime_weekdays = float(ded_overtime_weekdays)
    #         except:
    #             ded_overtime_weekdays = 50
    #
    #         try:
    #             ded_overtime_weekend = float(ded_overtime_weekend)
    #         except:
    #             ded_overtime_weekend = 100
    #
    #         try:
    #             ded_overtime_holiday = float(ded_overtime_holiday)
    #         except:
    #             ded_overtime_holiday = 0
    #         # tính thuế tncn
    #         limit_tax_personal = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_limit_tax_personal', 'False')
    #         limit_dependant = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_limit_dependant', 'False')
    #
    #         try:
    #             limit_tax_personal = float(limit_tax_personal)
    #         except:
    #             limit_tax_personal = 9000000
    #
    #         try:
    #             limit_dependant = float(limit_dependant)
    #         except:
    #             limit_dependant = 3600000
    #
    #         # ăn trưa
    #         price_lunch = self.env['ir.config_parameter'].sudo().get_param(
    #             'parameter_lunch', 'False')
    #
    #         try:
    #             price_lunch = float(price_lunch)
    #         except:
    #             price_lunch = 10000
    #
    #         # vals
    #         vals = {}
    #         # luong co ban va tro cap
    #         basic_contract = contract.wage
    #         allowance_fix_contract = contract.x_allowance_fix
    #         allowance_special_contract = contract.x_allowance_technique
    #         allowance_responsible_contract = contract.x_allowance_responsibility
    #         allowance_oil_contract = contract.x_allowance_travel
    #         allowance_phone_contract = contract.x_allowance_telephone
    #         allowance_diligence_contract = contract.x_allowance_diligence
    #         allowance_house_contract = contract.x_allowance_dwelling_house
    #         allowance_other_contract = contract.x_allowance_other
    #         total_contract = basic_contract + allowance_oil_contract + allowance_other_contract + \
    #                          allowance_phone_contract + allowance_diligence_contract + allowance_fix_contract \
    #                          + allowance_special_contract + allowance_responsible_contract + allowance_house_contract
    #         #  A. Lương và phụ cấp trên Hợp đồng
    #         vals.update(
    #             basic_contract=contract.wage,
    #             allowance_fix_contract=contract.x_allowance_fix,
    #             allowance_special_contract=contract.x_allowance_technique,
    #             allowance_responsible_contract=contract.x_allowance_responsibility,
    #             allowance_oil_contract=contract.x_allowance_travel,
    #             allowance_phone_contract=contract.x_allowance_telephone,
    #             allowance_diligence_contract=contract.x_allowance_diligence,
    #             allowance_house_contract=contract.x_allowance_dwelling_house,
    #             allowance_other_contract=contract.x_allowance_other,
    #         )
    #         # C.Lương cơ bản và các phụ cấp thực tế
    #         basic_real = contract.wage * ratio
    #         holiday_pay = total_contract * timsheet_employee.number_allow_leave / standard_workday
    #         allowance_fix_real = contract.x_allowance_fix * ratio  # co dinh
    #         allowance_special_real = contract.x_allowance_technique * ratio  # chuyên môn
    #         allowance_responsible_real = contract.x_allowance_responsibility * ratio  # trách nhiệm
    #         allowance_oil_real = contract.x_allowance_travel * ratio  # xăng xe, đi lại
    #         allowance_phone_real = contract.x_allowance_telephone * ratio  # điện thoại
    #         allowance_diligence_real = contract.x_allowance_diligence * ratio  # chuyên cần
    #         allowance_house_real = contract.x_allowance_dwelling_house * ratio  # nhà ở
    #         allowance_other_real = contract.x_allowance_other * ratio  # khác
    #         allowance_constructor_real = timsheet_employee.number_constructor * support_constructor
    #         vals.update(
    #             basic_real=basic_real,
    #             holiday_pay=holiday_pay,
    #             allowance_fix_real=allowance_fix_real,
    #             allowance_special_real=allowance_special_real,
    #             allowance_responsible_real=allowance_responsible_real,
    #             allowance_oil_real=allowance_oil_real,
    #             allowance_phone_real=allowance_phone_real,
    #             allowance_diligence_real=allowance_diligence_real,
    #             allowance_house_real=allowance_house_real,
    #             allowance_other_real=allowance_other_real,
    #             allowance_constructor_real=allowance_constructor_real,
    #         )
    #         # E.Lương làm việc tăng ca, PC đêm
    #         total_salary_cal_overtime = basic_contract + allowance_special_contract + allowance_responsible_contract
    #         overtime_weekday_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_weekdays * overtime_weekdays / real_workday / 8 / 100
    #         overtime_weekend_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_weekend * overtime_weekend / real_workday / 8 / 100
    #         overtime_holiday_salary = total_salary_cal_overtime * timsheet_employee.hour_overtime_holidays * overtime_holiday / real_workday / 8 / 100
    #         allowance_shift_night = total_salary_cal_overtime * timsheet_employee.hour_overtime_shift3 * overtime_shift_night / real_workday / 8 / 100
    #         vals.update(
    #             overtime_weekday_salary=overtime_weekday_salary,
    #             overtime_weekend_salary=overtime_weekend_salary,
    #             overtime_holiday_salary=overtime_holiday_salary,
    #             allowance_shift_night=allowance_shift_night,
    #         )
    #         # Tổng thu nhập miễn thuế trong tháng
    #         sickness_by_social = payroll_line.pay_for_social_insurance
    #         salary_overtime_night = contract.wage * ded_overtime_weekend * timsheet_employee.hour_overtime_weekend / real_workday / 8 / 100 + \
    #                                 contract.wage * ded_overtime_weekdays * timsheet_employee.hour_overtime_weekdays / real_workday / 8 / 100 \
    #                                 + contract.wage * ded_overtime_holiday * timsheet_employee.hour_overtime_holidays / 8 / 100 \
    #                                 + allowance_shift_night
    #
    #         allowance_phone = allowance_phone_real
    #         vals.update(
    #             sickness_by_social=sickness_by_social,
    #             salary_overtime_night=salary_overtime_night,
    #             allowance_phone=allowance_phone,
    #         )
    #         # F.Đóng BHXH
    #         vals.update(
    #             level_insurance=contract.x_salary
    #         )
    #         # G.Thuế thu nhập cá nhân
    #         allowances_family = limit_tax_personal + limit_dependant * payroll_line.number_person_dependant
    #         vals.update(
    #             allowances_family=allowances_family
    #         )
    #         # H.Các khoản khấu trừ khác
    #         total_lunch = timsheet_employee.number_lunch * price_lunch
    #         vals.update(
    #             total_lunch=total_lunch
    #         )
    #
    #         payroll_line.write(vals)
    #     self.write({
    #         'state': 'cal'
    #     })

    @api.multi
    def action_sent_approve(self):
        self.write({
            'state': 'wait'
        })

    @api.multi
    def action_approve(self):
        self.write({
            'state': 'approved'
        })

    @api.multi
    def action_payslip(self):
        if self.count_payslip > 0:
            return
        for payroll_line in self.lines:
            slip_data = self.env['hr.payslip'].with_context(contract=payroll_line.contract_id.id).onchange_employee_id(
                payroll_line.timesheet_line_id.timesheet_id.date_from,
                payroll_line.timesheet_line_id.timesheet_id.date_to, payroll_line.employee_id.id,
                payroll_line.contract_id.id)
            journal_id = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
            if len(journal_id) == 0:
                raise osv.except_orm("Cảnh báo!", "Vui lòng cấu hình Sổ nhật ký có loại là Chung hoặc Miscellaneous.")
            res = {
                'employee_id': payroll_line.employee_id.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': slip_data['value'].get('contract_id'),
                'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                'date_from': payroll_line.timesheet_line_id.timesheet_id.date_from,
                'date_to': payroll_line.timesheet_line_id.timesheet_id.date_to,
                'company_id': payroll_line.employee_id.company_id.id,
                'timesheet_line_id': payroll_line.timesheet_line_id.id,
                'timesheet_id': payroll_line.timesheet_line_id.timesheet_id.id,
                'payroll_line_id': payroll_line.id,
                'payroll_id': payroll_line.payroll_id.id,
                'journal_id': journal_id.id
            }
            payslip = self.env['hr.payslip'].create(res)
            for input in payslip.input_line_ids:
                vals = {}
                # PHU CAP CONG TRINH
                if input.code == 'PCCT':
                    vals.update(amount=payroll_line.allowance_constructor_real)
                # THANH TIEN TANG CA (DA QUY DOI)
                if input.code == 'TTTC':
                    vals.update(
                        amount=payroll_line.overtime_weekday_salary + payroll_line.overtime_weekend_salary + payroll_line.overtime_holiday_salary)
                # PHU CAP KHAC
                if input.code == 'PCK':
                    vals.update(amount=payroll_line.allowance_other_real)
                # CHI TRA HO BHXH
                if input.code == 'CTHBHXH':
                    vals.update(amount=payroll_line.pay_for_social_insurance)
                # TONG TIEN LE + PHEP + CHE DO
                if input.code == 'TTLPCD':
                    vals.update(amount=payroll_line.holiday_pay)
                # PHU CAP CA 3
                if input.code == 'PCC3':
                    vals.update(amount=payroll_line.allowance_shift_night)
                # TRUY LINH/ HO TRO KHAC
                if input.code == 'HTK':
                    vals.update(amount=payroll_line.other_revenue)
                # TRU COM
                if input.code == 'TC':
                    vals.update(amount=payroll_line.total_lunch)
                # PHAT DI MUON
                if input.code == 'DM':
                    vals.update(amount=payroll_line.total_mulct)
                # TAM UNG
                if input.code == 'TU':
                    vals.update(amount=payroll_line.advance_payment)
                # THUE TNCN TAM TINH
                if input.code == 'TTNCN':
                    vals.update(amount=payroll_line.total_tax_personal)
                if input.code == 'GROSSREAL':
                    vals.update(
                        amount=payroll_line.total_gross_contract - payroll_line.allowance_other_real - payroll_line.allowance_constructor_real - payroll_line.holiday_pay)
                input.write(vals)
            print(payslip.input_line_ids)
            payslip.compute_sheet()

    @api.multi
    def action_view_payslip(self):
        payslip_ids = self.mapped('payslip_ids')
        action = self.env.ref('hr_payroll.action_view_hr_payslip_form').read()[0]
        if len(payslip_ids) > 0:
            action['domain'] = [('id', 'in', payslip_ids.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def export_payroll(self):

        header_style = xlwt.easyxf("pattern: pattern solid, fore_color gray25; align: HORZ CENTER, VERT CENTER;font: height 280;\
                                                    borders: left thin, right thin, top thin,top_color black, bottom_color black, right_color black, left_color black; pattern: pattern solid;")

        editable = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;" \
                               "borders: left thin, right thin, top thin, bottom thin;")

        editable1 = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;pattern: pattern solid, fore_color gray25;" \
                                "borders: left thin, right thin, top thin, bottom thin;")
        editable2 = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;pattern: pattern solid, fore_color gray25;" \
                                "borders: left thin, right thin, top thin, bottom thin;font: color red;")

        editable3 = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;pattern: pattern solid, fore_color yellow;" \
                                "borders: left thin, right thin, top thin, bottom thin;")

        editable4 = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;pattern: pattern solid, fore_color pink;" \
                                "borders: left thin, right thin, top thin, bottom thin;")

        wb = xlwt.Workbook(encoding="UTF-8")
        date_str = str(datetime.today().date())
        ws = wb.add_sheet(date_str)

        ws.col(0).width = 10 * 500
        ws.col(1).width = 10 * 500
        ws.col(2).width = 10 * 500
        ws.col(3).width = 10 * 500
        ws.col(4).width = 10 * 500
        ws.col(5).width = 10 * 500
        ws.col(6).width = 10 * 500
        ws.col(7).width = 10 * 500
        ws.col(8).width = 10 * 500
        ws.col(9).width = 10 * 500
        ws.col(10).width = 10 * 500
        ws.col(11).width = 10 * 500
        ws.col(12).width = 10 * 500
        ws.col(13).width = 10 * 500
        ws.col(14).width = 10 * 500
        ws.col(15).width = 10 * 500
        ws.col(16).width = 10 * 500
        ws.col(17).width = 10 * 500
        ws.col(18).width = 10 * 500
        ws.col(19).width = 10 * 500
        ws.col(20).width = 10 * 500
        ws.col(21).width = 10 * 500
        ws.col(22).width = 10 * 500
        ws.col(23).width = 10 * 500
        ws.col(24).width = 10 * 500
        ws.col(25).width = 10 * 500
        ws.col(26).width = 10 * 500
        ws.col(27).width = 10 * 500
        ws.col(28).width = 10 * 500
        ws.col(29).width = 10 * 500
        ws.col(30).width = 10 * 500
        ws.col(31).width = 10 * 500
        ws.col(32).width = 10 * 500
        ws.col(33).width = 10 * 500
        ws.col(34).width = 10 * 500
        ws.col(35).width = 10 * 500
        ws.col(36).width = 10 * 500
        ws.col(37).width = 10 * 500
        ws.col(38).width = 10 * 500
        ws.col(39).width = 10 * 500
        ws.col(40).width = 10 * 500
        ws.col(41).width = 10 * 500
        ws.col(42).width = 10 * 500
        ws.col(43).width = 10 * 500
        ws.col(44).width = 10 * 500
        ws.col(45).width = 10 * 500
        ws.col(46).width = 10 * 500
        ws.col(47).width = 10 * 500
        ws.col(48).width = 10 * 500
        ws.col(49).width = 10 * 500
        ws.col(50).width = 10 * 500
        ws.col(51).width = 10 * 500
        ws.col(52).width = 10 * 500
        ws.col(53).width = 10 * 500
        ws.col(54).width = 10 * 500
        ws.col(55).width = 10 * 500
        ws.col(56).width = 10 * 500
        ws.col(57).width = 10 * 500
        ws.col(58).width = 10 * 500
        ws.col(59).width = 10 * 500
        ws.col(60).width = 10 * 500
        ws.col(61).width = 10 * 500
        ws.col(62).width = 10 * 500
        ws.col(63).width = 10 * 500
        ws.col(64).width = 10 * 500
        ws.col(65).width = 10 * 500
        ws.col(66).width = 10 * 500
        ws.col(67).width = 10 * 500
        ws.col(68).width = 10 * 500

        # ws.merge(0, 1, 0, 0, editable)
        # ws.merge(0, 1, 1, 1, editable)
        today = t_date.today()
        name = 'BẢNG LƯƠNG THÁNG %s NĂM %s' %(today.month, today.year)

        ws.merge(0, 0, 2, 7, editable)
        ws.merge(1, 1, 2, 7, editable)
        ws.write(0, 2, u'CÔNG TY CỔ PHẦN THH DECOR', header_style)
        ws.write(1, 2, name, header_style)

        # Thông tin nhân viên
        ws.merge(3, 6, 0, 0, editable1)
        ws.write(3, 0, u'STT', editable1)

        ws.merge(3, 6, 1, 1, editable1)
        ws.write(3, 1, u'MNV', editable1)

        ws.merge(3, 6, 2, 2, editable1)
        ws.write(3, 2, u'Họ và tên', editable1)

        ws.merge(3, 6, 3, 3, editable1)
        ws.write(3, 3, u'Vị trí', editable1)

        ws.merge(3, 6, 4, 4, editable1)
        ws.write(3, 4, u'Bộ phận', editable1)

        ws.merge(3, 6, 5, 5, editable1)
        ws.write(3, 5, u'Ngày vào làm việc', editable1)

        ws.merge(3, 6, 6, 6, editable1)
        ws.write(3, 6, u'Tình trạng hoạt động của HĐLĐ', editable1)

        ws.merge(3, 6, 7, 7, editable2)
        ws.write(3, 7, u'Ghi chú lương', editable2)

        # Lương và phụ cấp trên hợp đồng
        ws.merge(3, 4, 8, 16, editable2)
        ws.write(3, 8, u'A. Lương và phụ cấp trên Hợp đồng', editable2)

        ws.merge(5, 6, 8, 8, editable2)
        ws.write(5, 8, u'Lương cơ bản', editable2)

        ws.merge(5, 6, 9, 9, editable2)
        ws.write(5, 9, u'Phụ cấp cố định( xăng xe, điện thoại, độc hại)', editable2)

        ws.merge(5, 6, 10, 10, editable2)
        ws.write(5, 10, u'Phụ cấp chuyên môn', editable2)

        ws.merge(5, 6, 11, 11, editable2)
        ws.write(5, 11, u'Phụ cấp trách nhiệm', editable2)

        ws.merge(5, 6, 12, 12, editable2)
        ws.write(5, 12, u'Hỗ trợ xăng xe/đi lại', editable2)

        ws.merge(5, 6, 13, 13, editable2)
        ws.write(5, 13, u'Hỗ trợ điện thoại', editable2)

        ws.merge(5, 6, 14, 14, editable2)
        ws.write(5, 14, u'Phụ cấp chuyên cần', editable2)

        ws.merge(5, 6, 15, 15, editable2)
        ws.write(5, 15, u'Hỗ trợ nhà ở', editable2)

        ws.merge(5, 6, 16, 16, editable2)
        ws.write(5, 16, u'Phụ cấp khác', editable2)

        ws.merge(3, 6, 17, 17, editable2)
        ws.write(3, 17, u'Tổng thu nhập theo hợp đồng', editable2)

        # B.Ngày công thực tế
        ws.merge(3, 4, 18, 25, editable3)
        ws.write(3, 18, u'B.Ngày công thực tế', editable3)

        ws.merge(5, 6, 18, 18, editable3)
        ws.write(5, 18, u'Số ngày làm việc thực tế đã quy đổi', editable3)

        ws.merge(5, 6, 19, 19, editable3)
        ws.write(5, 19, u'Nghỉ phép', editable3)

        ws.merge(5, 6, 20, 20, editable3)
        ws.write(5, 20, u'Nghỉ lễ', editable3)

        ws.merge(5, 6, 21, 21, editable3)
        ws.write(5, 21, u'Nghỉ chế độ', editable3)

        ws.merge(5, 6, 22, 22, editable3)
        ws.write(5, 22, u'Nghỉ ốm', editable3)

        ws.merge(5, 6, 23, 23, editable3)
        ws.write(5, 23, u'Nghỉ thai sản', editable3)

        ws.merge(5, 6, 24, 24, editable3)
        ws.write(5, 24, u'Nghỉ không lương', editable3)

        ws.merge(5, 6, 25, 25, editable3)
        ws.write(5, 25, u'Nghỉ không lý do', editable3)

        # Lương cơ bản và các phụ cấp thực tế
        ws.merge(3, 4, 26, 37, editable2)
        ws.write(3, 26, u'C.Lương cơ bản và các phụ cấp thực tế', editable2)

        ws.merge(5, 6, 26, 26, editable2)
        ws.write(5, 26, u'Lương cơ bản', editable2)

        ws.merge(5, 6, 27, 27, editable2)
        ws.write(5, 27, u'Lương ngày phép/lễ/chế độ', editable2)

        ws.merge(5, 6, 28, 28, editable2)
        ws.write(5, 28, u'Phụ cấp cố định', editable2)

        ws.merge(5, 6, 29, 29, editable2)
        ws.write(5, 29, u'Phụ cấp chuyên môn', editable2)

        ws.merge(5, 6, 30, 30, editable2)
        ws.write(5, 30, u'Phụ cấp trách nhiệm', editable2)

        ws.merge(5, 6, 31, 31, editable2)
        ws.write(5, 31, u'Hỗ trợ xăng xe/đi lại', editable2)

        ws.merge(5, 6, 32, 32, editable2)
        ws.write(5, 32, u'Hỗ trợ điện thoại', editable2)

        ws.merge(5, 6, 33, 33, editable2)
        ws.write(5, 33, u'Phụ cấp chuyên cần', editable2)

        ws.merge(5, 6, 34, 34, editable2)
        ws.write(5, 34, u'Hỗ trợ nhà ở', editable2)

        ws.merge(5, 6, 35, 35, editable2)
        ws.write(5, 35, u'Phụ cấp công trình', editable2)

        ws.merge(5, 6, 36, 36, editable2)
        ws.write(5, 36, u'Phụ cấp khác', editable2)

        ws.merge(5, 6, 37, 37, editable2)
        ws.write(5, 37, u'Tổng lương và phụ cấp thực tế', editable2)

        # Số giờ làm việc ngày lễ,tăng ca,đêm
        ws.merge(3, 4, 38, 41, editable3)
        ws.write(3, 38, u'D.Số giờ làm việc ngày lễ, tăng ca, đêm', editable3)

        ws.merge(5, 6, 38, 38, editable3)
        ws.write(5, 38, u'Tăng ca ngày thường', editable3)

        ws.merge(5, 6, 39, 39, editable3)
        ws.write(5, 39, u'Tăng ca ngày nghỉ', editable3)

        ws.merge(5, 6, 40, 40, editable3)
        ws.write(5, 40, u'Tăng ca ngày Lễ', editable3)

        ws.merge(5, 6, 41, 41, editable3)
        ws.write(5, 41, u'Số giờ làm ca đêm', editable3)

        # Lương làm việc tăng ca,PC đêm
        ws.merge(3, 4, 42, 46, editable2)
        ws.write(3, 42, u'E.Lương làm việc tăng ca, PC đêm', editable2)

        ws.merge(5, 6, 42, 42, editable2)
        ws.write(5, 42, u'Tăng ca ngày thường', editable2)

        ws.merge(5, 6, 43, 43, editable2)
        ws.write(5, 43, u'Tăng ca ngày nghỉ', editable2)

        ws.merge(5, 6, 44, 44, editable2)
        ws.write(5, 44, u'Tăng ca ngày Lễ', editable2)

        ws.merge(5, 6, 45, 45, editable2)
        ws.write(5, 45, u'PC ca đêm', editable2)

        ws.merge(5, 6, 46, 46, editable2)
        ws.write(5, 46, u'Tổng tiền lương tăng ca +PC đêm', editable2)

        ws.merge(3, 6, 47, 47, editable2)
        ws.write(3, 47, u'Chi trả hộ BHXH', editable2)

        ws.merge(3, 6, 48, 48, editable2)
        ws.write(3, 48, u'Truy lĩnh/Khác', editable2)

        ws.merge(3, 6, 49, 49, editable2)
        ws.write(3, 49, u'Tổng thu nhập thực tế trong tháng', editable2)

        # Tổng thu thập miễn thuế trong tháng
        ws.merge(3, 4, 50, 53, editable2)
        ws.write(3, 50, u'Tổng thu nhập miễn thuế trong tháng', editable2)

        ws.merge(5, 6, 50, 50, editable2)
        ws.write(5, 50, u'Tiền ốm đau trả bởi bHXH', editable2)

        ws.merge(5, 6, 51, 51, editable2)
        ws.write(5, 51, u'Lương tăng ca +  PC đêm', editable2)

        ws.merge(5, 6, 52, 52, editable2)
        ws.write(5, 52, u'Hỗ trợ điện thoại', editable2)

        ws.merge(5, 6, 53, 53, editable2)
        ws.write(5, 53, u'Tổng tiền miễn thuế', editable2)

        # Đóng BHXH
        ws.merge(3, 4, 54, 55, editable2)
        ws.write(3, 54, u'F.Đóng BHXH', editable2)

        ws.merge(5, 6, 54, 54, editable2)
        ws.write(5, 54, u'Mức đóng', editable2)

        ws.merge(5, 6, 55, 55, editable2)
        ws.write(5, 55, u'Thành tiền', editable2)

        # Thuế thu nhập cá nhân
        ws.merge(3, 4, 56, 59, editable2)
        ws.write(3, 56, u'G.Thuế thu nhập cá nhân', editable2)

        ws.merge(5, 6, 56, 56, editable2)
        ws.write(5, 56, u'Số người phụ thuộc', editable2)

        ws.merge(5, 6, 57, 57, editable2)
        ws.write(5, 57, u'Giảm trừ gia cảnh', editable2)

        ws.merge(5, 6, 58, 58, editable2)
        ws.write(5, 58, u'Thu nhập chịu thuế', editable2)

        ws.merge(5, 6, 59, 59, editable2)
        ws.write(5, 59, u'Thuế TNCN', editable2)

        # Các khoản khấu trừ khác
        ws.merge(3, 4, 60, 64, editable2)
        ws.write(3, 60, u'H.Các khoản khấu trừ khác', editable2)

        ws.merge(5, 6, 60, 60, editable2)
        ws.write(5, 60, u'Tiền cơm', editable2)

        ws.merge(5, 6, 61, 61, editable2)
        ws.write(5, 61, u'Đi muộn, về sớm', editable2)

        ws.merge(5, 6, 62, 62, editable2)
        ws.write(5, 62, u'Tạm ứng', editable2)

        ws.merge(5, 6, 63, 63, editable2)
        ws.write(5, 63, u'Trừ khác', editable2)

        ws.merge(5, 6, 64, 64, editable2)
        ws.write(5, 64, u'Tổng khấu trừ', editable2)

        ws.merge(3, 6, 65, 65, editable2)
        ws.write(3, 65, u'Điều chỉnh hết TV', editable2)

        ws.merge(3, 6, 66, 66, editable2)
        ws.write(3, 66, u'Thực nhận', editable2)

        ws.merge(3, 6, 67, 67, editable2)
        ws.write(3, 67, u'Ghi chú', editable2)

        # Ngày công thực tế
        ws.write(7, 19, u'AL', editable)
        ws.write(7, 20, u'PH', editable)
        ws.write(7, 21, u'PL', editable)
        ws.write(7, 22, u'SL', editable)
        ws.write(7, 23, u'ML', editable)
        ws.write(7, 24, u'UL', editable)
        ws.write(7, 25, u'AP', editable)

        # Số giờ làm việc ngày lễ, tăng ca, đêm
        ws.write(7, 38, u'OT', editable)
        ws.write(7, 39, u'DO', editable)
        ws.write(7, 40, u'OPH', editable)
        ws.write(7, 41, u'S3', editable)

        # Thông tin nhân viên
        ws.merge(8, 10, 0, 0, editable)
        ws.write(8, 0, u'(1)', editable)

        ws.merge(8, 10, 1, 1, editable)
        ws.write(8, 1, u'(2)', editable)

        ws.merge(8, 10, 2, 2, editable)
        ws.write(8, 2, u'(3)', editable)

        ws.merge(8, 10, 3, 3, editable)
        ws.write(8, 3, u'(4)', editable)

        ws.merge(8, 10, 4, 4, editable)
        ws.write(8, 4, u'(5)', editable)

        ws.merge(8, 10, 5, 5, editable)
        ws.write(8, 5, u'(6)', editable)

        ws.merge(8, 10, 6, 6, editable)
        ws.write(8, 6, u'(7)', editable)

        ws.merge(8, 10, 7, 7, editable)
        ws.write(8, 7, '', editable)

        # Lương và phụ cấp trên Hợp đồng
        ws.merge(8, 10, 8, 8, editable)
        ws.write(8, 8, u'(8)', editable)

        ws.merge(8, 10, 9, 9, editable)
        ws.write(8, 9, u'(9)', editable)

        ws.merge(8, 10, 10, 10, editable)
        ws.write(8, 10, u'(10)', editable)

        ws.merge(8, 10, 11, 11, editable)
        ws.write(8, 11, u'(11)', editable)

        ws.merge(8, 10, 12, 12, editable)
        ws.write(8, 12, u'(12)', editable)

        ws.merge(8, 10, 13, 13, editable)
        ws.write(8, 13, u'(13)', editable)

        ws.merge(8, 10, 14, 14, editable)
        ws.write(8, 14, u'(14)', editable)

        ws.merge(8, 10, 15, 15, editable)
        ws.write(8, 15, u'(15)', editable)

        ws.merge(8, 10, 16, 16, editable)
        ws.write(8, 16, u'(16)', editable)

        ws.merge(8, 10, 17, 17, editable)
        ws.write(8, 17, u'((17)=(8)+(9)+(10)+(11)+(12)+(13)+(14)+(15)+(16))', editable)

        # Ngày công thực tế
        ws.merge(8, 10, 18, 18, editable)
        ws.write(8, 18, u'(18)', editable)

        ws.merge(8, 10, 19, 19, editable)
        ws.write(8, 19, u'(19)', editable)

        ws.merge(8, 10, 20, 20, editable)
        ws.write(8, 20, u'(20)', editable)

        ws.merge(8, 10, 21, 21, editable)
        ws.write(8, 21, u'(21)', editable)

        ws.merge(8, 10, 22, 22, editable)
        ws.write(8, 22, u'(22)', editable)

        ws.merge(8, 10, 23, 23, editable)
        ws.write(8, 23, u'(23)', editable)

        ws.merge(8, 10, 24, 24, editable)
        ws.write(8, 24, u'(24)', editable)

        ws.merge(8, 10, 25, 25, editable)
        ws.write(8, 25, u'(25)', editable)

        ws.merge(8, 10, 26, 26, editable)
        ws.write(8, 26, u'(26)', editable)

        ws.merge(8, 10, 27, 27, editable)
        ws.write(8, 27, u'(27)', editable)

        ws.merge(8, 10, 28, 28, editable)
        ws.write(8, 28, u'(28)', editable)

        ws.merge(8, 10, 29, 29, editable)
        ws.write(8, 29, u'(29)', editable)

        ws.merge(8, 10, 30, 30, editable)
        ws.write(8, 30, u'(30)', editable)

        ws.merge(8, 10, 31, 31, editable)
        ws.write(8, 31, u'(31)', editable)

        ws.merge(8, 10, 32, 32, editable)
        ws.write(8, 32, u'(32)', editable)

        ws.merge(8, 10, 33, 33, editable)
        ws.write(8, 33, u'(33)', editable)

        ws.merge(8, 10, 34, 34, editable)
        ws.write(8, 34, u'(34)', editable)

        ws.merge(8, 10, 35, 35, editable)
        ws.write(8, 35, u'(35)', editable)

        ws.merge(8, 10, 36, 36, editable)
        ws.write(8, 36, u'(36)', editable)

        # Số giờ làm việc ngày lễ, tăng ca, đêm
        ws.merge(8, 10, 37, 37, editable)
        ws.write(8, 37, u'(37)', editable)

        ws.merge(8, 10, 38, 38, editable)
        ws.write(8, 38, u'(38)', editable)

        ws.merge(8, 10, 39, 39, editable)
        ws.write(8, 39, u'(39)', editable)

        ws.merge(8, 10, 40, 40, editable)
        ws.write(8, 40, u'(40)', editable)

        ws.merge(8, 10, 41, 41, editable)
        ws.write(8, 41, u'(41)', editable)

        # Lương làm việc tăng ca, PC đêm
        ws.merge(8, 10, 42, 42, editable)
        ws.write(8, 42, u'(42)', editable)

        ws.merge(8, 10, 43, 43, editable)
        ws.write(8, 43, u'(43)', editable)

        ws.merge(8, 10, 44, 44, editable)
        ws.write(8, 44, u'(44)', editable)

        ws.merge(8, 10, 45, 45, editable)
        ws.write(8, 45, u'(45)', editable)

        ws.merge(8, 10, 46, 46, editable)
        ws.write(8, 46, u'(46)', editable)

        # Truy lĩnh/Khác
        ws.merge(8, 10, 48, 48, editable)
        # Tổng thu nhập thực tế trong tháng
        ws.write(8, 48, u'(47)', editable)

        # Tổng thu nhập miễn thuế trong tháng
        ws.merge(8, 10, 49, 49, editable)
        ws.write(8, 49, u'(48)', editable)

        ws.merge(8, 10, 50, 50, editable)
        ws.write(8, 50, u'(49)', editable)

        ws.merge(8, 10, 51, 51, editable)
        ws.write(8, 51, u'(50)', editable)

        ws.merge(8, 10, 52, 52, editable)
        ws.write(8, 52, u'', editable)

        ws.merge(8, 10, 53, 53, editable)
        ws.write(8, 53, u'(51)', editable)

        # Đóng BHXH
        ws.merge(8, 10, 54, 54, editable)
        ws.write(8, 54, u'(52)', editable)

        ws.merge(8, 10, 55, 55, editable)
        ws.write(8, 55, u'(53)', editable)

        # Thuế thu nhập cá nhân
        ws.merge(8, 10, 56, 56, editable)
        ws.write(8, 56, u'(54)', editable)

        ws.merge(8, 10, 57, 57, editable)
        ws.write(8, 57, u'(55)', editable)

        ws.merge(8, 10, 58, 58, editable)
        ws.write(8, 58, u'(56)', editable)

        ws.merge(8, 10, 59, 59, editable)
        ws.write(8, 59, u'(57)', editable)

        # Các khoản khấu trừ khác
        ws.merge(8, 10, 60, 60, editable)
        ws.write(8, 60, u'(58)', editable)

        ws.merge(8, 10, 61, 61, editable)
        ws.write(8, 61, u'(59)', editable)

        ws.merge(8, 10, 62, 62, editable)
        ws.write(8, 62, u'(60)', editable)

        ws.merge(8, 10, 63, 63, editable)
        ws.write(8, 63, u'(61)', editable)

        ws.merge(8, 10, 64, 64, editable)
        ws.write(8, 64, u'(62)', editable)

        # Điều chỉnh hết TV
        ws.merge(8, 10, 65, 65, editable)
        ws.write(8, 65, u'', editable)

        # Thực nhận
        ws.merge(8, 10, 66, 66, editable)
        ws.write(8, 66, u'(63)', editable)

        # Ghi chú
        ws.merge(8, 10, 67, 67, editable)
        ws.write(8, 67, u'(64)', editable)
        index = 12
        i = 1
        # count = 0
        total_contract = 0
        total_allowance_constructor_real = 0
        total_allowance_fix_contract = 0
        total_allowance_special_contract = 0
        total_allowance_responsible_contract = 0
        total_allowance_oil_contract = 0
        total_allowance_phone_contract = 0
        total_allowance_diligence_real = 0
        total_allowance_house_real = 0
        total_allowance_house_real = 0
        total_real_workday = 0
        number_allow_leave = 0
        number_holiday_leave = 0
        number_policy_leave = 0
        number_sick_leave = 0
        number_maternity_leave = 0
        number_unpaid_leave = 0
        number_unreasonal_leave = 0
        basic_real = 0
        holiday_pay = 0
        allowance_fix_real = 0
        allowance_special_real = 0
        allowance_responsible_real = 0
        allowance_oil_real = 0
        allowance_phone_real = 0
        allowance_diligence_real = 0
        allowance_house_real = 0
        allowance_other_real = 0

        total_gross_real = 0
        hour_overtime_weekdays = 0
        hour_overtime_weekend = 0
        hour_overtime_holidays = 0
        hour_overtime_shift3 = 0
        overtime_weekday_salary = 0
        overtime_weekend_salary = 0
        overtime_holiday_salary = 0
        allowance_shift_night = 0
        total_overtime_salary = 0
        pay_for_social_insurance = 0
        other_revenue = 0
        total_gross_month = 0
        sickness_by_social = 0
        salary_overtime_night = 0
        allowance_phone = 0
        total_deduction_tax_personal = 0
        level_insurance = 0
        total_insurance = 0
        number_person_dependant = 0
        allowances_family = 0
        gross_taxed_personal = 0
        total_tax_personal = 0
        total_lunch = 0
        total_mulct = 0
        advance_payment = 0
        x_allowance_other = 0
        ded_other = 0
        total_deduction = 0
        total_end_trail = 0
        total_net = 0
        total_total_gross_contract = 0
        for k, g in groupby(self.lines, lambda x: x.department_id):
            employees = list(g)
            print(k)
            print(len(k))
            print(employees)
            count = 0

            for emp in employees:
                open_date = emp.open_date.strftime('%d/%m/%Y')

                ws.write(index, 0, i, editable)
                ws.write(index, 1, emp.employee_id.x_code, editable)
                ws.write(index, 2, emp.employee_id.name, editable)
                ws.write(index, 3, emp.contract_id.job_id.name, editable)
                ws.write(index, 4, emp.department_id.name, editable)
                ws.write(index, 5, open_date, editable)
                ws.write(index, 6, emp.contract_id.state, editable)
                ws.write(index, 7, '', editable)
                ws.write(index, 8, emp.basic_contract, editable)
                ws.write(index, 9, emp.allowance_fix_contract, editable)
                ws.write(index, 10, emp.allowance_special_contract, editable)
                ws.write(index, 11, emp.allowance_responsible_contract, editable)
                ws.write(index, 12, emp.allowance_oil_contract, editable)
                ws.write(index, 13, emp.allowance_phone_contract, editable)
                ws.write(index, 14, emp.allowance_diligence_real, editable)
                ws.write(index, 15, emp.allowance_house_real, editable)
                ws.write(index, 16, emp.allowance_other_contract, editable)
                ws.write(index, 17, emp.total_gross_contract, editable)
                # Ngày công thực tế
                ws.write(index, 18, emp.timesheet_line_id.real_workday, editable)
                ws.write(index, 19, emp.timesheet_line_id.number_allow_leave, editable)
                ws.write(index, 20, emp.timesheet_line_id.number_holiday_leave, editable)
                ws.write(index, 21, emp.timesheet_line_id.number_policy_leave, editable)
                ws.write(index, 22, emp.timesheet_line_id.number_sick_leave, editable)
                ws.write(index, 23, emp.timesheet_line_id.number_maternity_leave, editable)
                ws.write(index, 24, emp.timesheet_line_id.number_unpaid_leave, editable)
                ws.write(index, 25, emp.timesheet_line_id.number_unreasonal_leave, editable)
                # Lương cơ bản và phụ cấp
                ws.write(index, 26, emp.basic_real, editable)
                ws.write(index, 27, emp.holiday_pay, editable)
                ws.write(index, 28, emp.allowance_fix_real, editable)
                ws.write(index, 29, emp.allowance_special_real, editable)
                ws.write(index, 30, emp.allowance_responsible_real, editable)
                ws.write(index, 31, emp.allowance_oil_real, editable)
                ws.write(index, 32, emp.allowance_phone_real, editable)
                ws.write(index, 33, emp.allowance_diligence_real, editable)
                ws.write(index, 34, emp.allowance_house_real, editable)
                ws.write(index, 35, '', editable)
                ws.write(index, 36, emp.allowance_other_real, editable)
                ws.write(index, 37, emp.total_gross_real, editable)
                # Số giờ làm việc ngày lễ, tăng ca, đêm
                ws.write(index, 38, emp.timesheet_line_id.hour_overtime_weekdays, editable)
                ws.write(index, 39, emp.timesheet_line_id.hour_overtime_weekend, editable)
                ws.write(index, 40, emp.timesheet_line_id.hour_overtime_holidays, editable)
                ws.write(index, 41, emp.timesheet_line_id.hour_overtime_shift3, editable)
                # Lương làm việc tăng ca, PC đêm
                ws.write(index, 42, emp.overtime_weekday_salary, editable)
                ws.write(index, 43, emp.overtime_weekend_salary, editable)
                ws.write(index, 44, emp.overtime_holiday_salary, editable)
                ws.write(index, 45, emp.allowance_shift_night, editable)
                ws.write(index, 46, emp.total_overtime_salary, editable)

                # Chi trả hộ BHXH
                ws.write(index, 47, emp.pay_for_social_insurance, editable)

                # Truy lĩnh/Khác
                ws.write(index, 48, emp.other_revenue, editable)

                # Tổng thu nhập thực tế trong tháng
                ws.write(index, 49, emp.total_gross_month, editable)

                # Tổng thu nhập miễn thuế trong tháng
                ws.write(index, 50, emp.sickness_by_social, editable)
                ws.write(index, 51, emp.salary_overtime_night, editable)
                ws.write(index, 52, emp.allowance_phone, editable)
                ws.write(index, 53, emp.total_deduction_tax_personal, editable)

                # Đóng BHXH
                ws.write(index, 54, emp.level_insurance, editable)
                ws.write(index, 55, emp.total_insurance, editable)

                # Thuế TNCN
                ws.write(index, 56, emp.number_person_dependant, editable)
                ws.write(index, 57, emp.allowances_family, editable)
                ws.write(index, 58, emp.gross_taxed_personal, editable)
                ws.write(index, 59, emp.total_tax_personal, editable)

                # Các khoản khấu trừ khác
                ws.write(index, 60, emp.total_lunch, editable)
                ws.write(index, 61, emp.total_mulct, editable)
                ws.write(index, 62, emp.advance_payment, editable)
                ws.write(index, 63, emp.ded_other, editable)
                ws.write(index, 64, emp.total_deduction, editable)

                # Điều chỉnh hết TV
                ws.write(index, 65, emp.total_end_trail, editable)

                # Thực nhận
                ws.write(index, 66, emp.total_net, editable)

                # Ghi chú
                ws.write(index, 67, emp.note, editable)

                if len(employees) == 1:
                    # Thông tin cá nhân
                    ws.write(index + 1, 1, emp.department_id.name, editable4)

                    ws.write(index + 1, 2, '', editable4)
                    ws.write(index + 1, 3, '', editable4)
                    ws.write(index + 1, 4, '', editable4)
                    ws.write(index + 1, 5, '', editable4)
                    ws.write(index + 1, 6, '', editable4)
                    ws.write(index + 1, 7, '', editable4)

                    # Lương và phụ cấp trên hợp đồng
                    ws.write(index + 1, 8, emp.basic_contract, editable4)
                    ws.write(index + 1, 9, emp.allowance_fix_contract, editable4)
                    ws.write(index + 1, 10, emp.allowance_special_contract, editable4)
                    ws.write(index + 1, 11, emp.allowance_responsible_contract, editable4)
                    ws.write(index + 1, 12, emp.allowance_oil_contract, editable4)
                    ws.write(index + 1, 13, emp.allowance_phone_contract, editable4)
                    ws.write(index + 1, 14, emp.allowance_diligence_real, editable4)
                    ws.write(index + 1, 15, emp.allowance_house_real, editable4)
                    ws.write(index + 1, 16, emp.allowance_other_contract, editable4)
                    ws.write(index + 1, 17, emp.total_gross_contract, editable4)

                    # Ngày công thực tế
                    ws.write(index + 1, 18, emp.timesheet_line_id.real_workday, editable4)
                    ws.write(index + 1, 19, emp.timesheet_line_id.number_allow_leave, editable4)
                    ws.write(index + 1, 20, emp.timesheet_line_id.number_holiday_leave, editable4)
                    ws.write(index + 1, 21, emp.timesheet_line_id.number_policy_leave, editable4)
                    ws.write(index + 1, 22, emp.timesheet_line_id.number_sick_leave, editable4)
                    ws.write(index + 1, 23, emp.timesheet_line_id.number_maternity_leave, editable4)
                    ws.write(index + 1, 24, emp.timesheet_line_id.number_unpaid_leave, editable4)
                    ws.write(index + 1, 25, emp.timesheet_line_id.number_unreasonal_leave, editable4)

                    # Lương cơ bản và các phụ cấp thực tế
                    ws.write(index + 1, 26, emp.basic_real, editable4)
                    ws.write(index + 1, 27, emp.holiday_pay, editable4)
                    ws.write(index + 1, 28, emp.allowance_fix_real, editable4)
                    ws.write(index + 1, 29, emp.allowance_special_real, editable4)
                    ws.write(index + 1, 30, emp.allowance_responsible_real, editable4)
                    ws.write(index + 1, 31, emp.allowance_oil_real, editable4)
                    ws.write(index + 1, 32, emp.allowance_phone_real, editable4)
                    ws.write(index + 1, 33, emp.allowance_diligence_real, editable4)
                    ws.write(index + 1, 34, emp.allowance_house_real, editable4)
                    ws.write(index + 1, 35, emp.allowance_constructor_real, editable4)
                    ws.write(index + 1, 36, emp.allowance_other_real, editable4)
                    ws.write(index + 1, 37, emp.total_gross_real, editable4)

                    # Số giờ làm việc ngày lễ, tăng ca, đêm
                    ws.write(index + 1, 38, emp.timesheet_line_id.hour_overtime_weekdays, editable4)
                    ws.write(index + 1, 39, emp.timesheet_line_id.hour_overtime_weekend, editable4)
                    ws.write(index + 1, 40, emp.timesheet_line_id.hour_overtime_holidays, editable4)
                    ws.write(index + 1, 41, emp.timesheet_line_id.hour_overtime_shift3, editable4)

                    # Lương làm việc tăng ca, PC đêm
                    ws.write(index + 1, 42, emp.overtime_weekday_salary, editable4)
                    ws.write(index + 1, 43, emp.overtime_weekend_salary, editable4)
                    ws.write(index + 1, 44, emp.overtime_holiday_salary, editable4)
                    ws.write(index + 1, 45, emp.allowance_shift_night, editable4)
                    ws.write(index + 1, 46, emp.total_overtime_salary, editable4)

                    # Chi trả hộ BHXH
                    ws.write(index + 1, 47, emp.pay_for_social_insurance, editable4)

                    # Truy lĩnh khác
                    ws.write(index + 1, 48, emp.other_revenue, editable4)

                    # Tổng thu nhập thực tế trong tháng
                    ws.write(index + 1, 49, emp.total_gross_month, editable4)

                    # Tổng tiền miễn thuế trong tháng
                    ws.write(index + 1, 50, emp.sickness_by_social, editable4)
                    ws.write(index + 1, 51, emp.salary_overtime_night, editable4)
                    ws.write(index + 1, 52, emp.allowance_phone, editable4)
                    ws.write(index + 1, 53, emp.total_deduction_tax_personal, editable4)

                    # Đóng BHXH
                    ws.write(index + 1, 54, emp.level_insurance, editable4)
                    ws.write(index + 1, 55, emp.total_insurance, editable4)

                    # Thuế TNCN
                    ws.write(index + 1, 56, emp.number_person_dependant, editable4)
                    ws.write(index + 1, 57, emp.allowances_family, editable4)
                    ws.write(index + 1, 58, emp.gross_taxed_personal, editable4)
                    ws.write(index + 1, 59, emp.total_tax_personal, editable4)

                    # Các khoản khấu trừ khác
                    ws.write(index + 1, 60, emp.total_lunch, editable4)
                    ws.write(index + 1, 61, emp.total_mulct, editable4)
                    ws.write(index + 1, 62, emp.advance_payment, editable4)
                    ws.write(index + 1, 63, emp.ded_other, editable4)
                    ws.write(index + 1, 64, emp.total_deduction, editable4)

                    # Điều chỉnh hết TV
                    ws.write(index + 1, 65, emp.total_end_trail, editable4)

                    # Thực nhận
                    ws.write(index + 1, 66, emp.total_net, editable4)
                    index += 1
                if len(employees) != 1:
                    count += 1
                    total_allowance_constructor_real += emp.allowance_constructor_real
                    total_contract += emp.basic_contract
                    total_allowance_fix_contract += emp.allowance_fix_contract
                    total_allowance_special_contract += emp.allowance_special_contract
                    total_allowance_responsible_contract += emp.allowance_responsible_contract
                    total_allowance_oil_contract += emp.allowance_oil_contract
                    total_allowance_phone_contract += emp.allowance_phone_contract
                    total_allowance_diligence_real += emp.allowance_diligence_real
                    total_allowance_diligence_real += emp.allowance_diligence_real
                    total_total_gross_contract += emp.total_gross_contract
                    total_real_workday += emp.timesheet_line_id.real_workday
                    number_allow_leave += emp.timesheet_line_id.number_allow_leave
                    number_holiday_leave += emp.timesheet_line_id.number_holiday_leave
                    number_policy_leave += emp.timesheet_line_id.number_policy_leave
                    number_sick_leave += emp.timesheet_line_id.number_sick_leave
                    number_maternity_leave += emp.timesheet_line_id.number_maternity_leave
                    number_unpaid_leave += emp.timesheet_line_id.number_unpaid_leave
                    number_unreasonal_leave += emp.timesheet_line_id.number_unreasonal_leave
                    basic_real += emp.basic_real
                    holiday_pay += emp.holiday_pay
                    allowance_fix_real += emp.allowance_fix_real
                    allowance_special_real += emp.allowance_special_real
                    allowance_responsible_real += emp.allowance_responsible_real
                    allowance_oil_real += emp.allowance_oil_real
                    allowance_phone_real += emp.allowance_phone_real
                    allowance_diligence_real += emp.allowance_diligence_real
                    allowance_house_real += emp.allowance_house_real
                    allowance_other_real += emp.allowance_other_real
                    total_gross_real += emp.total_gross_real
                    # total_gross_real += emp.total_gross_real
                    hour_overtime_weekdays += emp.timesheet_line_id.hour_overtime_weekdays
                    hour_overtime_weekend += emp.timesheet_line_id.hour_overtime_weekend
                    hour_overtime_holidays += emp.timesheet_line_id.hour_overtime_holidays
                    hour_overtime_shift3 += emp.timesheet_line_id.hour_overtime_shift3
                    overtime_weekday_salary += emp.overtime_weekday_salary
                    overtime_weekend_salary += emp.overtime_weekend_salary
                    overtime_holiday_salary += emp.overtime_holiday_salary
                    allowance_shift_night += emp.allowance_shift_night
                    total_overtime_salary += emp.total_overtime_salary
                    pay_for_social_insurance += emp.pay_for_social_insurance
                    other_revenue += emp.other_revenue
                    total_gross_month += emp.total_gross_month
                    sickness_by_social += emp.sickness_by_social
                    salary_overtime_night += emp.salary_overtime_night
                    allowance_phone += emp.allowance_phone
                    total_deduction_tax_personal += emp.total_deduction_tax_personal
                    level_insurance += emp.level_insurance
                    total_insurance += emp.total_insurance
                    number_person_dependant += emp.number_person_dependant
                    allowances_family += emp.allowances_family
                    gross_taxed_personal += emp.gross_taxed_personal
                    total_tax_personal += emp.total_tax_personal
                    total_lunch += emp.total_lunch
                    total_mulct += emp.total_mulct
                    advance_payment += emp.advance_payment
                    ded_other += emp.ded_other
                    total_deduction += emp.total_deduction
                    total_end_trail += emp.total_end_trail
                    total_net += emp.total_net
                    x_allowance_other += emp.contract_id.x_allowance_other

                    if count == len(employees):
                        # Thông tin cá nhân
                        ws.write(index + 1, 1, emp.department_id.name, editable4)
                        #
                        ws.write(index + 1, 2, '', editable4)
                        ws.write(index + 1, 3, '', editable4)
                        ws.write(index + 1, 4, '', editable4)
                        ws.write(index + 1, 5, '', editable4)
                        ws.write(index + 1, 6, '', editable4)
                        ws.write(index + 1, 7, '', editable4)

                        ws.write(index + 1, 8, total_contract, editable4)
                        ws.write(index + 1, 9, total_allowance_fix_contract, editable4)
                        ws.write(index + 1, 10, total_allowance_special_contract, editable4)
                        ws.write(index + 1, 11, total_allowance_responsible_contract, editable4)
                        ws.write(index + 1, 12, total_allowance_oil_contract, editable4)
                        ws.write(index + 1, 13, total_allowance_phone_contract, editable4)
                        ws.write(index + 1, 14, total_allowance_diligence_real, editable4)
                        ws.write(index + 1, 15, total_allowance_house_real, editable4)
                        ws.write(index + 1, 16, x_allowance_other, editable4)
                        ws.write(index + 1, 17, total_total_gross_contract, editable4)

                        # Ngày công thực tế
                        ws.write(index + 1, 18, total_real_workday, editable4)
                        ws.write(index + 1, 19, number_allow_leave, editable4)
                        ws.write(index + 1, 20, number_holiday_leave, editable4)
                        ws.write(index + 1, 21, number_policy_leave, editable4)
                        ws.write(index + 1, 22, number_sick_leave, editable4)
                        ws.write(index + 1, 23, number_maternity_leave, editable4)
                        ws.write(index + 1, 24, number_unpaid_leave, editable4)
                        ws.write(index + 1, 25, number_unreasonal_leave, editable4)

                        # Lương cơ bản và các phụ cấp thực tế
                        ws.write(index + 1, 26, basic_real, editable4)
                        ws.write(index + 1, 27, holiday_pay, editable4)
                        ws.write(index + 1, 28, allowance_fix_real, editable4)
                        ws.write(index + 1, 29, allowance_special_real, editable4)
                        ws.write(index + 1, 30, allowance_responsible_real, editable4)
                        ws.write(index + 1, 31, allowance_oil_real, editable4)
                        ws.write(index + 1, 32, allowance_phone_real, editable4)
                        ws.write(index + 1, 33, allowance_diligence_real, editable4)
                        ws.write(index + 1, 34, allowance_house_real, editable4)
                        ws.write(index + 1, 35, total_allowance_constructor_real, editable4)
                        ws.write(index + 1, 36, allowance_other_real, editable4)
                        ws.write(index + 1, 37, total_gross_real, editable4)

                        # Số giờ làm việc ngày lễ, tăng ca, đêm
                        ws.write(index + 1, 38, hour_overtime_weekdays, editable4)
                        ws.write(index + 1, 39, hour_overtime_weekend, editable4)
                        ws.write(index + 1, 40, hour_overtime_holidays, editable4)
                        ws.write(index + 1, 41, hour_overtime_shift3, editable4)

                        # Lương làm việc tăng ca, PC đêm
                        ws.write(index + 1, 42, overtime_weekday_salary, editable4)
                        ws.write(index + 1, 43, overtime_weekend_salary, editable4)
                        ws.write(index + 1, 44, overtime_holiday_salary, editable4)
                        ws.write(index + 1, 45, allowance_shift_night, editable4)
                        ws.write(index + 1, 46, total_overtime_salary, editable4)

                        # Chi trả hộ BHXH
                        ws.write(index + 1, 47, pay_for_social_insurance, editable4)

                        # Truy lĩnh/Khác
                        ws.write(index + 1, 48, other_revenue, editable4)

                        # Tổng thu nhập thực tế trong tháng
                        ws.write(index + 1, 49, total_gross_month, editable4)

                        # Tổng thu nhập miễn thuế trong tháng
                        ws.write(index + 1, 50, sickness_by_social, editable4)
                        ws.write(index + 1, 51, salary_overtime_night, editable4)
                        ws.write(index + 1, 52, allowance_phone, editable4)
                        ws.write(index + 1, 53, total_deduction_tax_personal, editable4)

                        # Đóng BHXH
                        ws.write(index + 1, 54, level_insurance, editable4)
                        ws.write(index + 1, 55, total_insurance, editable4)

                        # Thuế thu nhập cá nhân
                        ws.write(index + 1, 56, number_person_dependant, editable4)
                        ws.write(index + 1, 57, allowances_family, editable4)
                        ws.write(index + 1, 58, gross_taxed_personal, editable4)
                        ws.write(index + 1, 59, total_tax_personal, editable4)

                        # Các khoản khấu trừ khác
                        ws.write(index + 1, 60, total_lunch, editable4)
                        ws.write(index + 1, 61, total_mulct, editable4)
                        # ws.write(index + 1, 62, advance_payment, editable4)
                        ws.write(index + 1, 63, ded_other, editable4)
                        ws.write(index + 1, 64, total_deduction, editable4)

                        # Điều chỉnh hết TV
                        ws.write(index + 1, 65, total_end_trail, editable4)

                        # Thực nhận
                        ws.write(index + 1, 66, total_net, editable4)

                        index += 1
                        # index -= len(employees)

                index += 1
                i += 1

        stream = stringIOModule.BytesIO()
        wb.save(stream)
        xls = stream.getvalue()
        vals = {
            'name': date_str + '.xls',
            'datas': base64.b64encode(xls),
            'datas_fname': date_str + '.xls',
            'type': 'binary',
            'res_model': 'hr.payroll',
            'res_id': self.id,
        }
        file_xls = self.env['ir.attachment'].create(vals)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/' + str(file_xls.id) + '?download=true',
            'target': 'new',
        }

    def import_payroll(self):
        try:
            if not self._check_format_excel(self.file_name):
                raise osv.except_osv("Cảnh báo!",
                                     (
                                         "File không được tìm thấy hoặc không đúng định dạng. Vui lòng kiểm tra lại định dạng file .xls hoặc .xlsx"))
            data = base64.decodebytes(self.upload_file)
            excel = xlrd.open_workbook(file_contents=data, encoding_override="cp1252")
            sheet = excel.sheet_by_index(0)
            index = 1
            res = self.env['hr.payroll.line'].search([('payroll_id', '=', self.id)])
            if res:
                for i in res:
                    while index < sheet.nrows:
                        pay_for_social_insurance = sheet.cell(index, 3).value
                        other_revenue = sheet.cell(index, 4).value
                        sickness_by_social = sheet.cell(index, 5).value
                        number_person_dependant = sheet.cell(index, 6).value
                        total_mulct = sheet.cell(index, 7).value

                        ded_other = sheet.cell(index, 9).value
                        total_end_trail = sheet.cell(index, 10).value

                        val = {
                            'pay_for_social_insurance': pay_for_social_insurance,
                            'other_revenue': other_revenue,
                            'sickness_by_social': sickness_by_social,
                            'number_person_dependant': number_person_dependant,
                            'total_mulct': total_mulct,
                            # 'advance_payment':'',
                            'ded_other': ded_other,
                            'total_end_trail': total_end_trail,
                        }
                        i.write(val)
                        index += 1
                        break
                    self.upload_file = None
                    self.file_name = None
            else:
                raise ValidationError("Bạn vui lòng kiểm tra lại!")
        except ValueError as e:
            raise osv.except_osv("Warning!", (e))

    def _check_format_excel(self, file_name):
        if file_name == False:
            return False
        if file_name.endswith('xls') == False and file_name.endswith('xlsx') == False:
            return False
        return True

    @api.multi
    def download_template(self):
        header_style = xlwt.easyxf("pattern: pattern solid, fore_color gray25; align: HORZ CENTER, VERT CENTER;font: height 280;\
                                                        borders: left thin, right thin, top thin,top_color black, bottom_color black, right_color black, left_color black; pattern: pattern solid;")

        editable = xlwt.easyxf("align: HORZ CENTER, VERT CENTER;font: height 280;" \
                               "borders: left thin, right thin, top dotted, bottom dotted;")
        wb = xlwt.Workbook(encoding="UTF-8")
        date_str = str(datetime.today().date())
        ws = wb.add_sheet(date_str)

        ws.col(0).width = 10 * 500
        ws.write(0, 0, u'Mã nhân viên', header_style)

        ws.col(1).width = 10 * 500
        ws.write(0, 1, u'Họ tên', header_style)

        ws.col(2).width = 10 * 500
        ws.write(0, 2, u'Hợp đồng', header_style)

        ws.col(3).width = 10 * 500
        ws.write(0, 3, u'Chi trả hộ BHXH', header_style)

        ws.col(4).width = 10 * 500
        ws.write(0, 4, u'Truy lĩnh/khác', header_style)

        ws.col(5).width = 10 * 500
        ws.write(0, 5, u'Ốm đau trả bởi BHXH', header_style)

        ws.col(6).width = 10 * 500
        ws.write(0, 6, u'Số người phụ thuộc', header_style)

        ws.col(7).width = 10 * 500
        ws.write(0, 7, u'Đi muộn về sớm', header_style)

        ws.col(8).width = 10 * 500
        ws.write(0, 8, u'Tạm ứng', header_style)

        ws.col(9).width = 10 * 500
        ws.write(0, 9, u'Trừ khác', header_style)

        ws.col(10).width = 10 * 500
        ws.write(0, 10, u'Điều chỉnh hết TV', header_style)

        index = 1
        for line in self.lines:
            ws.write(index, 1, line.employee_id.name, editable)
            ws.write(index, 0, line.employee_id.x_code, editable)
            ws.write(index, 2, line.contract_id.name, editable)
            ws.write(index, 3, line.pay_for_social_insurance, editable)
            ws.write(index, 4, line.other_revenue, editable)
            ws.write(index, 5, line.sickness_by_social, editable)
            ws.write(index, 6, line.number_person_dependant, editable)
            ws.write(index, 7, line.total_mulct, editable)
            # ws.write(index, 8, line.advance_payment, editable)
            ws.write(index, 9, line.ded_other, editable)
            ws.write(index, 10, line.total_end_trail, editable)
            index += 1

        stream = stringIOModule.BytesIO()
        wb.save(stream)
        xls = stream.getvalue()
        vals = {
            'name': date_str + '.xls',
            'datas': base64.b64encode(xls),
            'datas_fname': date_str + '.xls',
            'type': 'binary',
            'res_model': 'hr.payroll',
            'res_id': self.id,
        }
        file_xls = self.env['ir.attachment'].create(vals)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/' + str(file_xls.id) + '?download=true',
            'target': 'new',
        }

    @api.multi
    def action_print(self):
        return {
            'type': 'ir.actions.act_url',
            'url': 'report/pdf/izi_hr_nesta_custom.report_payroll_template/%s' % (self.id),
            'target': 'new',
            'res_id': self.id,
        }

    @api.model
    def get_email_info(self):
        parameter_email_payroll = self.env['ir.config_parameter'].sudo().get_param(
            'parameter_email_payroll', 'False')
        return parameter_email_payroll

    @api.model
    def get_phone_info(self):
        parameter_phone_payroll = self.env['ir.config_parameter'].sudo().get_param(
            'parameter_phone_payroll', 'False')
        return parameter_phone_payroll



    @api.multi
    def action_sent_salary_emp(self):
        if self.lines:
            for record in self:
                for emp in record.lines:
                    if emp.employee_id.user_id.id:
                        partner_id = emp.employee_id.user_id.partner_id
                    else:
                        partner_id = emp.employee_id.address_home_id

                    mail = self.env['izi.sent.mail.template'].create({
                                'name': '[NESTA-HR] V/v thông báo bảng lương cho tháng ' + str(
                                    emp.timesheet_line_id.timesheet_id.name) + '.',
                                'model': 'hr.payroll.line',
                                'res_id': emp.id,
                                'partner_id': partner_id.id,
                                'content_before': 'Chi tiết bảng lương tháng' + str(emp.timesheet_line_id.timesheet_id.name),
                                'content': ' Của nhân viên ' + str(emp.employee_id.name),
                                'content_after': 'Để xem chi tiết, bạn vui lòng click chọn vào button dưới đây. Xin cảm ơn.'
                            })
                    thread_var = threading.Thread(target=mail.action_send_mail_major(True, True))
                    thread_var.start()
        else:
            raise ValidationError('Phải có ít nhất 1 nhân viên.Xin cám ơn!')


    @api.multi
    def action_hr_manager_confirm(self):
        for state in self:
            state.state = 'wait'

    @api.multi
    def action_admin_confirm(self):
        for state in self:
            state.state = 'approved'

class HrPayrollLine(models.Model):
    _name = 'hr.payroll.line'
    _description = 'Payroll Line'
    _rec_name = 'employee_id'

    payroll_id = fields.Many2one('hr.payroll', string="Payroll", ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    department_id = fields.Many2one('hr.department', string="Department")
    open_date = fields.Date(string="Open Date")
    timesheet_line_id = fields.Many2one('hr.timesheet.line', string="Timesheet Line")
    timesheet_id = fields.Many2one('hr.timesheet', related='timesheet_line_id.timesheet_id', string="Timesheet")
    contract_id = fields.Many2one('hr.contract', string="Contract")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", ondelete="restrict")
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Payslip Run", ondelete="restrict")

    # follow contract
    basic_contract = fields.Float(string="Basic Contract")
    allowance_fix_contract = fields.Float(string="Allowance Fix Contract")
    allowance_special_contract = fields.Float(string="Allowance Special Contract")
    allowance_responsible_contract = fields.Float(string="Allowance Responsible Contract")
    allowance_oil_contract = fields.Float(string="Allowance Oil Contract")
    allowance_phone_contract = fields.Float(string="Allowance Phone Contract")
    allowance_diligence_contract = fields.Float(string="Allowance Diligence Contract")
    allowance_house_contract = fields.Float(string="Allowance House Contract")
    allowance_other_contract = fields.Float(string="Allowance Other Contract")
    total_gross_contract = fields.Float(string="Total Gross Contract", compute="_compute_total_gross_contract",
                                        store=True)

    # follow real
    basic_real = fields.Float(string="Basic Real")
    holiday_pay = fields.Float(string="Holiday Pay")
    allowance_fix_real = fields.Float(string="Allowance Fix Real")
    allowance_special_real = fields.Float(string="Allowance Special Real")
    allowance_responsible_real = fields.Float(string="Allowance Responsible Real")
    allowance_oil_real = fields.Float(string="Allowance Oil Real")
    allowance_phone_real = fields.Float(string="Allowance Phone Real")
    allowance_diligence_real = fields.Float(string="Allowance Diligence Real")
    allowance_house_real = fields.Float(string="Allowance House Real")
    allowance_constructor_real = fields.Float(string="Allowance Constructor")
    allowance_other_real = fields.Float(string="Allowance Other Real")
    total_gross_real = fields.Float(string="Total Gross Real", compute="_compute_total_gross_real", store=True)

    # tăng ca, làm đêm
    overtime_weekday_salary = fields.Float(string="Overtime on weekdays")
    overtime_weekend_salary = fields.Float(string="Overtime on weekends")
    overtime_holiday_salary = fields.Float(string="Overtime on holidays")
    allowance_shift_night = fields.Float(string="Allowance Shift Night")
    total_overtime_salary = fields.Float(string="Total Overtime Salary", compute="_compute_total_overtime_salary",
                                         store=True)

    # chi tra ho bhxh
    pay_for_social_insurance = fields.Float(string="Pay for Social Insurance")
    other_revenue = fields.Float(string="Other Revenues")

    # total real month
    total_gross_month = fields.Float(string="Total Gross Month", compute="_compute_total_gross_month", store=True)

    # deduction tax personal
    sickness_by_social = fields.Float(string="Sickness paid by Social Insurance")
    salary_overtime_night = fields.Float(string="Overtime Pay and Night Allowance")
    allowance_phone = fields.Float(string="Allowance Phone")
    total_deduction_tax_personal = fields.Float(string="Total Deduction Tax Personal",
                                                compute="_compute_total_deduction_tax_personal", store=True)

    # Social Insurance
    level_insurance = fields.Float(string="Level Insurance")
    total_insurance = fields.Float(string="Total Insurance", compute="_compute_total_insurance", store=True)

    # tax personal
    number_person_dependant = fields.Float(string="Number Person Dependant")
    allowances_family = fields.Float(string="Allowances Family", compute="_compute_allowances_family", store=True)
    gross_taxed_personal = fields.Float(string="Gross Taxed Personal", compute="_compute_gross_taxed_personal",
                                        store=True)
    total_tax_personal = fields.Float(string="Total Tax Personal", compute="_compute_total_tax_personal", store=True)



    # Deduction other
    total_lunch = fields.Float(string="Deduction Lunch")
    total_mulct = fields.Float(string="Mulct Late, Early")
    advance_payment = fields.Float(string="Advance Payment")
    ded_other = fields.Float(string="Deduction Other")
    total_deduction = fields.Float(string="Total Deduction Other", compute="_compute_total_deduction", store=True)

    # điều chỉnh hết TV
    total_end_trail = fields.Float(string="Total End Trail")

    # thực nhận
    total_net = fields.Float(string="NET", compute="_compute_total_net", store=True)
    note = fields.Text(string="Note")

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id.id:
            self.department_id = self.employee_id.department_id.id
            self.open_date = self.employee_id.x_start_date
            contract = self.env['hr.contract'].sudo().search(
                [('state', 'in', ['open', 'pending']), ('employee_id', '=', self.employee_id.id)])
            if len(contract) == 1:
                self.contract_id = contract.id
            else:
                raise exceptions.ValidationError(
                    "Đang tồn tại nhiều hơn 1 hợp đồng có hiệu lực. Vui lòng lựa chọn.")

    @api.onchange('pay_for_social_insurance')
    def onchange_pay_for_social_insurance(self): # tiền ốm đau chi trả bởi BHXH
        self.sickness_by_social = self.pay_for_social_insurance

    @api.depends('basic_contract', 'allowance_fix_contract', 'allowance_special_contract',
                 'allowance_responsible_contract', 'allowance_oil_contract', 'allowance_phone_contract',
                 'allowance_diligence_contract', 'allowance_house_contract', 'allowance_other_contract'
                 )
    def _compute_total_gross_contract(self):
        for record in self:
            record.total_gross_contract = record.basic_contract + record.allowance_fix_contract + \
                                          record.allowance_special_contract + record.allowance_responsible_contract + \
                                          record.allowance_oil_contract + record.allowance_phone_contract + \
                                          record.allowance_diligence_contract + record.allowance_house_contract + record.allowance_other_contract

    @api.depends('basic_real', 'allowance_fix_real', 'allowance_special_real', 'holiday_pay',
                 'allowance_responsible_real', 'allowance_oil_real', 'allowance_phone_real',
                 'allowance_diligence_real', 'allowance_house_real', 'allowance_other_real',
                 'allowance_constructor_real'
                 )
    def _compute_total_gross_real(self):
        for record in self: # Tổng lương và phụ cấp thực tế
            record.total_gross_real = record.basic_real + record.allowance_fix_real + record.holiday_pay + \
                                      record.allowance_special_real + record.allowance_responsible_real + \
                                      record.allowance_oil_real + record.allowance_phone_real + \
                                      record.allowance_diligence_real + record.allowance_house_real + record.allowance_constructor_real + record.allowance_other_real

    @api.depends('overtime_weekday_salary', 'overtime_holiday_salary', 'allowance_shift_night',
                 'overtime_weekend_salary')
    def _compute_total_overtime_salary(self):
        for record in self:
            record.total_overtime_salary = record.overtime_weekday_salary + record.overtime_weekend_salary + record.overtime_holiday_salary + record.allowance_shift_night

    @api.depends('total_gross_real', 'total_overtime_salary', 'pay_for_social_insurance', 'other_revenue')
    def _compute_total_gross_month(self): # Thu nhập thực tế trong tháng
        for record in self:
            record.total_gross_month = record.pay_for_social_insurance + record.other_revenue + record.total_overtime_salary + record.total_gross_real

    @api.depends('sickness_by_social', 'overtime_weekday_salary', 'allowance_phone', 'overtime_holiday_salary', 'overtime_weekend_salary')
    def _compute_total_deduction_tax_personal(self): #Tổng tiền miễn thuế
        for record in self:
            orver_time_config = self.env['hr.timesheet.overtime.config'].search([('state', '=', 'active')], limit=1)

            ded_overtime_weekday_salary = record.overtime_weekday_salary - (record.overtime_weekday_salary / orver_time_config.percent_night)
            ded_overtime_weekend_salary = record.overtime_weekend_salary - (record.overtime_weekend_salary / orver_time_config.percent_weekend)
            ded_overtime_holiday_salary = record.overtime_holiday_salary - (record.overtime_holiday_salary / orver_time_config.percent_holiday)
            # record.total_deduction_tax_personal = record.sickness_by_social + record.total_overtime_salary + record.allowance_phone + record.total_deduction_tax_personal
            record.total_deduction_tax_personal = record.sickness_by_social + ded_overtime_weekday_salary + ded_overtime_weekend_salary + ded_overtime_holiday_salary + record.allowance_phone + record.total_deduction_tax_personal
                                                # Tiền ốm đau chi trả bởi BHXH + giảm trừ làm thêm + Hỗ trợ điện thoại +
    @api.depends('level_insurance')
    def _compute_total_insurance(self): #Tổng tiền đóng bảo hiểm
        for record in self:
            record.total_insurance = record.level_insurance * (
                    record.contract_id.x_contribution_employee_social + record.contract_id.x_contribution_employee_medical
                    + record.contract_id.x_contribution_employee_unemployment + record.contract_id.x_contribution_employee_labor_accidents) / 100

    @api.depends('number_person_dependant')
    def _compute_allowances_family(self): # giảm trừ gia cảnh
        # limit_tax_personal = self.env['ir.config_parameter'].sudo().get_param(
        #     'parameter_limit_tax_personal', 'False')
        limit_tax_personal = self.env['hr.personal.income.tax.config'].sudo().search([('state', '=', 'active')], limit=1)
        limit_dependant = self.env['ir.config_parameter'].sudo().get_param(
            'parameter_limit_dependant', 'False')

        try:
            limit_tax_personal = float(limit_tax_personal.personal_income_tax_limit)
        except:
            limit_tax_personal = 9000000

        try:
            limit_dependant = float(limit_tax_personal.deduction_dependant_limit)
        except:
            limit_dependant = 3600000
        for record in self:
            record.allowances_family = limit_tax_personal + record.number_person_dependant * limit_dependant

    @api.depends('total_gross_month', 'total_deduction_tax_personal', 'total_insurance', 'allowances_family')
    def _compute_gross_taxed_personal(self): #  thu nhập chịu thuế
        for record in self:
            total = record.total_gross_month - record.total_deduction_tax_personal - record.total_insurance - record.allowances_family
                    # Thu nhập thực tế trong tháng - tổng tiền miễn thuế - tiền đóng bảo hiểm - giảm trừ gia cảnh
            if total <= 0:
                total = 0
            record.gross_taxed_personal = total

    @api.depends('gross_taxed_personal')
    def _compute_total_tax_personal(self): # Tổng thuế TNCN phải nộp
        for record in self:
            tax_line = self.env['hr.personal.income.tax.line'].search(
                [('income_id.state', '=', 'active'), ('amount', '>', record.gross_taxed_personal)], order='amount')
            if len(tax_line) > 0:
                record.total_tax_personal = record.gross_taxed_personal * tax_line[0].percent / 100
            else:
                if record.gross_taxed_personal > 0 and record.gross_taxed_personal <= 5000000:
                    record.total_tax_personal = record.gross_taxed_personal * 5 / 100
                elif record.gross_taxed_personal > 5000000 and record.gross_taxed_personal <= 10000000:
                    record.total_tax_personal = record.gross_taxed_personal * 10 / 100
                elif record.gross_taxed_personal > 10000000 and record.gross_taxed_personal <= 18000000:
                    record.total_tax_personal = record.gross_taxed_personal * 15 / 100
                elif record.gross_taxed_personal > 18000000 and record.gross_taxed_personal <= 32000000:
                    record.total_tax_personal = record.gross_taxed_personal * 20 / 100
                elif record.gross_taxed_personal > 32000000 and record.gross_taxed_personal <= 52000000:
                    record.total_tax_personal = record.gross_taxed_personal * 25 / 100
                elif record.gross_taxed_personal > 52000000 and record.gross_taxed_personal <= 80000000:
                    record.total_tax_personal = record.gross_taxed_personal * 30 / 100
                elif record.gross_taxed_personal > 80000000:
                    record.total_tax_personal = record.gross_taxed_personal * 35 / 100
                else:
                    record.total_tax_personal = -1

    @api.depends('total_lunch', 'total_mulct', 'ded_other', 'advance_payment')
    def _compute_total_deduction(self): # Tổng khấu trừ
        for record in self:
            record.total_deduction = record.total_lunch + record.total_mulct + record.ded_other + record.advance_payment

    @api.depends('total_gross_month', 'total_insurance', 'total_tax_personal', 'total_deduction')
    def _compute_total_net(self): # Thực lĩnh
        for record in self:
            record.total_net = record.total_gross_month - record.total_insurance - record.total_tax_personal - record.total_deduction

    @api.multi
    def action_print_line(self):
        return {
            'type': 'ir.actions.act_url',
            'url': 'report/pdf/izi_hr_nesta_custom.report_payroll_line_template/%s' % (self.id),
            'target': 'new',
            'res_id': self.id,
        }

    @api.model
    def get_email_info(self):
        parameter_email_payroll = self.env['ir.config_parameter'].sudo().get_param(
            'parameter_email_payroll', 'False')
        return parameter_email_payroll

    @api.model
    def get_phone_info(self):
        parameter_phone_payroll = self.env['ir.config_parameter'].sudo().get_param(
            'parameter_phone_payroll', 'False')
        return parameter_phone_payroll
