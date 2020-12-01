# -*- coding: utf-8 -*-

from odoo import models, fields, api
import datetime as datetime_new
from odoo.osv import osv


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_date_range = fields.Date(string="Date Range")
    x_address_range = fields.Char(string="Address Range")
    x_relative = fields.One2many('hr.employee.relative', 'employee_id', string="Relative information")
    x_code_company = fields.Many2one('hr.res.company', 'Company')
    x_start_date = fields.Date("Work Start Date", default=datetime_new.date.today(), track_visibility='onchange')
    x_end_date = fields.Date('Work End Date', track_visibility='onchange')
    x_trial_end_date = fields.Date('Trial End Date', track_visibility='onchange')
    x_main_job = fields.Char('Main Job')
    x_code = fields.Char(string="Employee code")
    x_rank = fields.Selection([('NV', 'Employee'), ('QL', 'Manager'), ('GD', 'Director')], 'Rank', default='NV',
                              track_visibility='onchange')
    x_level = fields.Char('Level', track_visibility='onchange')
    x_school = fields.Char('School')
    x_speciality = fields.Char('Speciality')
    x_born = fields.Char(string="Born")
    x_nation = fields.Char(string="Nation", default="Kinh")
    x_religion = fields.Char(string="Religion", default="Không")
    x_tax_code = fields.Char(string="Tax Code")
    address_home_id = fields.Many2one(
        'res.partner', 'Private Address',
        help='Enter here the private address of the employee, not the one linked to your company.',
        groups="hr.group_hr_user,base.group_user")

    @api.model
    def default_get(self, fields):
        res = super(HrEmployee, self).default_get(fields)
        if 'category_ids' in fields:
            ids = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.category_default', 'False')
            try:
                ids = [int(ids)]
            except:
                ids = []
            res['category_ids'] = ids
        if 'x_code_company' in fields:
            ids = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.code_company_default', 'False')
            try:
                ids = [int(ids)]
            except:
                ids = []
            company_id = self.env['hr.res.company'].browse(ids)
            res['x_code_company'] = company_id.id
        if 'work_location' in fields:
            res['work_location'] = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.work_location_company_default', '')
        if 'x_trial_end_date' in fields:
            res['x_trial_end_date'] = datetime_new.date.today() + datetime_new.timedelta(2 * 365 / 12)
        if 'work_phone' in fields:
            res['work_phone'] = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.work_phone_default_hr_employee', '')
        if 'country_of_birth' in fields:
            res['country_of_birth'] =  self.env['res.country'].search([('code','=','VN')]).id
        if 'country_id' in fields:
            res['country_id'] =  self.env['res.country'].search([('code','=','VN')]).id

        return res

    @api.onchange('address_id')
    def _onchange_address_id(self):
        if not self.ids and not self.department_id.id:
            self.work_phone = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.work_phone_default_hr_employee', '')


    @api.onchange('department_id')
    def _onchange_department(self):
        super(HrEmployee, self)._onchange_department()
        if not self.department_id.id:
            ids = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_vi_hr_payroll.manager_default_hr_employee', 'False')
            try:
                id = int(ids)
                self.parent_id = id
            except:
                pass

    @api.multi
    def name_get(self):
        res = []
        for emp in self:
            code = emp.x_code or "-"
            res.append((emp.id, '[' + code + '] ' + emp.name))
        return res

    @api.model
    def create(self, vals):
        if vals.get('x_code_company') != False:
            code_com = self.env['hr.res.company'].browse([vals['x_code_company']])
            seq = code_com.sequence.next_by_id()
            name = code_com.code_company + '-'
            vals['x_code'] = name + seq
        else:
            raise osv.except_orm('Cảnh báo', 'Vui lòng chọn phòng ban cho nhân viên này.')
        res = super(HrEmployee, self).create(vals)
        return res

    @api.one
    def write(self, vals):
        res = super(HrEmployee, self).write(vals)
        if 'x_code_company' in vals.keys():
            com_id = self.env['hr.res.company'].browse([vals['x_code_company']])
            seq = com_id.sequence.next_by_id()
            self.write({'x_code': com_id.code_company + '.' + seq})
        return res


class RelativeHrEmployee(models.Model):
    _name = 'hr.employee.relative'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    name = fields.Char(string="Name relative")
    relationship = fields.Selection([('dad', 'Dad'),
                                     ('mother', 'Mother'),
                                     ('children', 'Children'),
                                     ('wife', 'Wife'),
                                     ('husband', 'Husband'), ('other', 'Other')])
    birthday = fields.Date('Date of Birth')
    work_email = fields.Char('Work Email')
    work_phone = fields.Char('Work Phone')


class CodeCompany(models.Model):
    _name = "hr.res.company"

    name = fields.Char("Company")
    code_company = fields.Char("Code Company")
    sequence = fields.Many2one('ir.sequence')

    _sql_constraints = [('code_company_unique', 'UNIQUE(code_company)', "Mã công ty là duy nhất"), ]

    # @api.one
    def _create_sequence(self, name, code):
        sequence = self.env['ir.sequence'].create({
            'name': name,
            'code': code,
            'number_increment': 1,
            'number_next': 1,
            'padding': 5,
            'implementation': 'standard',
        })
        return sequence.id

    @api.model
    def create(self, vals):
        if vals.get('name') and vals.get('code_company'):
            sq = self._create_sequence(vals.get('name'), vals.get('code_company'))
            vals['sequence'] = sq
        return super(CodeCompany, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('name'):
            if vals.get('code_company'):
                sq = self._create_sequence(vals.get('name'), vals.get('code_company'))
            else:
                sq = self._create_sequence(vals.get('name'), self.code_company)
            self.sequence = sq
        return super(CodeCompany, self).write(vals)
