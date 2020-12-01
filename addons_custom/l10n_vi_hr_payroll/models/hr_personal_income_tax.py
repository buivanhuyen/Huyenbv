# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime
from odoo.osv import osv


class HrIncomeTax(models.Model):
    _name = 'hr.personal.income.tax.config'

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")

    personal_income_tax_limit = fields.Float(string="Personal Income Tax Limit", default=0)
    deduction_dependant_limit = fields.Float(string="Deduction Dependants Limit", default=0)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive')], default="draft")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrIncomeTax, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False


class HrPersonalIncomeTax(models.Model):
    _name = 'hr.personal.income.tax.rate'

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    incomes = fields.One2many('hr.personal.income.tax.line', 'income_id', string="Incomes")
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive')], default="draft")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrPersonalIncomeTax, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False

class HrPersonalIncomeTaxLine(models.Model):
    _name = 'hr.personal.income.tax.line'

    income_id = fields.Many2one('hr.personal.income.tax.rate')
    amount = fields.Float(string="Amount")
    percent = fields.Float(string="Percent")



class HrDependant(models.Model):
    _name = 'hr.dependant'

    def default_personal_income_tax(self):
        insurance_id = self.env['hr.personal.income.tax.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].personal_income_tax_limit
        else:
            return 0

    def default_deduction_dependants(self):
        insurance_id = self.env['hr.personal.income.tax.config'].search(
            [('active', '=', True), ('date_from', '<=', datetime.date.today())], limit=1)
        if insurance_id.id:
            return insurance_id[0].deduction_dependant_limit
        else:
            return 0

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    x_dependants = fields.Float(string="Dependants", default=0, copy=True)
    x_personal_income_tax = fields.Float(string="Personal Income Taxt", copy=False, default=default_personal_income_tax)
    x_deduction_dependants = fields.Float(string="Deduction Dependants", default=default_deduction_dependants)
    state = fields.Selection([('draft','Draft'),('active','Active'),('inactive','Inactive')], default="draft")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrDependant, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False


