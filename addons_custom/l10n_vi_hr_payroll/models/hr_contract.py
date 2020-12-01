# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime


class HrContract(models.Model):
    _inherit = "hr.contract"

    def default_contribution_employee_social(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_employee_social
        else:
            return 0

    def default_contribution_company_social(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_company_social
        else:
            return 0

    def default_contribution_employee_medical(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_employee_medical
        else:
            return 0

    def default_contribution_company_medical(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_company_medical
        else:
            return 0

    def default_contribution_employee_unemployment(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_employee_unemployment
        else:
            return 0

    def default_contribution_company_unemployment(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_company_unemployment
        else:
            return 0

    def default_contribution_employee_labor_accidents(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_employee_labor_accidents
        else:
            return 0

    def default_contribution_company_labor_accidents(self):
        insurance_id = self.env['hr.insurance.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].contribution_company_labor_accidents
        else:
            return 0

    x_standard_work = fields.Float(string="Standard Work")
    x_salary = fields.Float(string="Insurance premiums")
    x_start_date = fields.Date(string="Start Date")
    x_contribution_employee_social = fields.Float(string="Contribution employee social",
                                                  default=default_contribution_employee_social)
    x_contribution_company_social = fields.Float(string="Contribution company social",
                                                 default=default_contribution_company_social)
    x_contribution_employee_medical = fields.Float(string="Contribution employee medical",
                                                   default=default_contribution_employee_medical)
    x_contribution_company_medical = fields.Float(string="Contribution company medical",
                                                  default=default_contribution_company_medical)
    x_contribution_employee_unemployment = fields.Float(string="Contribution employee unemployment",
                                                        default=default_contribution_employee_unemployment)
    x_contribution_company_unemployment = fields.Float(string="Contribution company unemployment",
                                                       default=default_contribution_company_unemployment)
    x_contribution_employee_labor_accidents = fields.Float(string="Contribution employee labor accidents",
                                                           default=default_contribution_employee_labor_accidents)
    x_contribution_company_labor_accidents = fields.Float(string="Contribution company labor accidents",
                                                          default=default_contribution_company_labor_accidents)
    x_num_visa = fields.Integer(string="Number Visa")
    x_num_work_license = fields.Char(string="The number work license")
    x_finish_date_visa = fields.Date(string="Finish date visa")
    # Định nghĩa các khoản phụ cấp
    x_allowance_lunch = fields.Float(string="Allowance Lunch", copy=True)
    x_allowance_travel_comm = fields.Float(string="Allowance Travel and Communication", copy=True)
    x_allowance_housing = fields.Float(string="Allowance House", copy=True)

    line_ids = fields.One2many('hr.contract.history.insurance', 'contract_id', required=False, readonly=True,
                               string="History Deitail")

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            self.name = self.employee_id.x_code


class HrContractHistoryInsuranceLine(models.Model):
    _name = "hr.contract.history.insurance"

    contract_id = fields.Many2one('hr.contract')
    contribution_employee_social = fields.Float(string="Contribution Employee Social")
    contribution_employee_medical = fields.Float(string="Contribution Employee Medical")
    contribution_employee_unemployment = fields.Float(string="Contribution Employee Unemployment")
    contribution_company_social = fields.Float(string="Contribution Company Social")
    contribution_company_medical = fields.Float(string="Contribution Company Medical")
    contribution_company_unemployment = fields.Float(string="Contribution Company Unemployment")
    contribution_salary = fields.Float(string="Contribution Salary")
    date = fields.Date("Start Date")
