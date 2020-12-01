# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import except_orm
from odoo.osv import osv
from datetime import datetime
import base64
import xlrd
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


#  Cau hinh muc dong bao hiem va thay doi ti le dong bao hiem
class HrConfigInsurance(models.Model):
    _name = 'hr.insurance.config'

    name = fields.Char(string="Name")
    active = fields.Boolean(string="Active", default=True)
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")

    contribution_employee_social = fields.Float(string="Credit contribution employee social", default=0)
    contribution_company_social = fields.Float(string="Credit contribution company social", default=0)
    contribution_employee_medical = fields.Float(string="Credit contribution employee medical", default=0)
    contribution_company_medical = fields.Float(string="Credit contribution company medical", default=0)
    contribution_employee_unemployment = fields.Float(string="Credit contribution employee unemployment", default=0)
    contribution_company_unemployment = fields.Float(string="Credit contribution company unemployment", default=0)
    contribution_employee_labor_accidents = fields.Float(string="Contribution employee labor accidents", default=0)
    contribution_company_labor_accidents = fields.Float(string="Contribution company labor accidents", default=0)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('inactive', 'Inactive')], default="draft")

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm("Cảnh báo!", "Bạn không thể xóa khi khác trạng thái Dự thảo.")
        return super(HrConfigInsurance, self).unlink()

    @api.multi
    def action_active(self):
        self.state = 'active'
        contracts = self.env["hr.contract"].search([('state', 'in', ['draft', 'open'])])
        for contract in contracts:
            vals_history = {
                'contribution_employee_social': contract.x_contribution_employee_social or False,
                'contribution_company_social': contract.x_contribution_company_social or False,
                'contribution_employee_unemployment': contract.x_contribution_employee_unemployment or False,
                'contribution_company_unemployment': contract.x_contribution_company_unemployment or False,
                'contribution_employee_medical': contract.x_contribution_employee_medical or False,
                'contribution_company_medical': contract.x_contribution_company_medical or False,
                'date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'contract_id': contract.id
            }
            self.env['hr.contract.history.insurance'].create(vals_history)
            contract.write({
                'x_contribution_employee_social': self.contribution_employee_social or 0,
                'x_contribution_company_social': self.contribution_company_social or 0,
                'x_contribution_employee_medical': self.contribution_employee_medical or 0,
                'x_contribution_company_medical': self.contribution_company_medical or 0,
                'x_contribution_employee_unemployment': self.contribution_employee_unemployment or 0,
                'x_contribution_company_unemployment': self.contribution_company_unemployment or 0,
                'x_contribution_employee_labor_accidents': self.contribution_employee_labor_accidents or 0,
                'x_contribution_company_labor_accidents': self.contribution_company_labor_accidents or 0,
            })

    @api.multi
    def action_inactive(self):
        self.state = 'inactive'
        self.active = False


# Thay doi ti le dong bao hiem
class HrAdjustInsuranceContribute(models.Model):
    _name = 'hr.adjust.insurance.contribute'

    name = fields.Char(string="Name")
    adjust_date = fields.Date(string="Adjust Date", default=fields.Date.today)
    state = fields.Selection(selection=(('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')), default='draft')
    contribute_line_ids = fields.One2many('hr.adjust.insurance.contribute.line', 'contribute_id',
                                          string='Detail Adjust')
    field_binary_import = fields.Binary(string="Field Binary Import")
    field_binary_name = fields.Char("Field Binary Name")

    @api.onchange('name', 'adjust_date')
    def onchange_name(self):
        str_mes = u'Điều chỉnh mức đóng bảo hiểm ngày '
        if self.adjust_date:
            str_mes += str(datetime.strptime(str(self.adjust_date), '%Y-%m-%d').strftime('%d'))
            str_mes += ' tháng ' + str(datetime.strptime(str(self.adjust_date), '%Y-%m-%d').strftime('%m'))
            str_mes += ' năm ' + str(datetime.strptime(str(self.adjust_date), '%Y-%m-%d').strftime('%Y'))
        self.name = str_mes

    @api.multi
    def action_confirm(self):
        if len(self.contribute_line_ids) == 0:
            raise osv.except_orm("Cảnh báo!", "Bạn cần tạo thông tin điều chỉnh cho nhân viên")
        else:
            self.state = "confirm"

    @api.multi
    def action_back(self):
        for line in self.contribute_line_ids:
            line.unlink()
        self.state = 'draft'

    @api.multi
    def action_done(self):
        for line in self.contribute_line_ids:
            if line.contract_id:
                obj_contract_insurance = self.env['hr.contract.history.insurance']
                vals = {
                    'contribution_salary': line.contribution_level,
                    'date': line.contract_id.x_start_date,
                    'contract_id': line.contract_id.id
                }
                obj_contract_insurance.create(vals)
                vals_contract = {
                    'x_salary': line.contribution_level,
                    'x_start_date': line.application_date,
                }
                line.contract_id.update(vals_contract)
        self.update({'state': 'done'})

    @api.onchange('contribute_line_ids')
    def onchange_line(self):
        if len(self.contribute_line_ids) > 0:
            for line in self.contribute_line_ids:
                line.contribute_id.name = self.name

    @api.multi
    def dowmload_templates_file_xlsx(self):
        # self.detail_ids.unlink()
        param_obj = self.env['ir.config_parameter']  # replace self.pool.get('ir.config_parameter')
        base_url = param_obj.get_param(
            'web.base.url')  # replace param_obj.get_param(self._cr, self._uid, 'web.base.url')
        url = base_url + '/l10n_vi_hr_payroll/static/description/file_template_contribution_insurance.xlsx'
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "_parent",
        }

    @api.constrains('contribute_line_ids')
    def contranis_employee(self):
        if len(self.contribute_line_ids) > 0:
            for line in self.contribute_line_ids:
                obj_hr_employee = self.env['hr.employee'].search([('id', '=', line.employee_id.id)])
                obj_contribute = self.env['hr.adjust.insurance.contribute.line'].search(
                    [('employee_id', '=', line.employee_id.id), ('contribute_id', '=', line.contribute_id.id)])
                if len(obj_contribute) > 1:
                    raise ValidationError(_("nhân viên " + str(obj_hr_employee.name_related) + " đã được điều chỉnh"))

                obj_contracr = self.env['hr.contract'].search(
                    [('employee_id', '=', line.employee_id.id), ('state', '=', 'open')])
                if len(obj_contracr) == 0:
                    raise ValidationError(
                        _("Bạn phải tạo hợp đồng đang chạy cho nhân viên " + str(obj_hr_employee.name_related) + "này"))

    @api.multi
    def action_hr_insurance_by_employees(self):
        user = self.env['res.users']  # replace self.env['res.users'].browse([self._uid])
        data_obj = self.env['ir.model.data']  # replace self.pool['ir.model.data']
        context = dict(self.env.context).copy()
        view = data_obj.xmlid_to_res_id(
            'l10n_vi_hr_payroll.view_hr_insurance_by_employees')  # replace data_obj.xmlid_to_res_id(self._cr, self._uid, 'izi_hr_insurrance.adjust_contribute_by_employees')
        context.update({
            'default_contribute_id': self.id,
        })
        return {
            'name': _('Message'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'hr.insurance.employees',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'action': 'action_hr_insurance_by_employees',
            'context': context,
        }

    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def check_format_file_import(self, field_name):
        if not field_name:
            return False
        if field_name.endswith('.xls') == False and field_name.endswith('.xlsx') == False:
            return False
        return True

    @api.multi
    def update_data(self, vals):
        if self.field_binary_import:
            try:
                lines = []
                if not self.check_format_file_import(self.field_binary_name):
                    raise osv.except_osv('Cảnh báo!',
                                         (
                                             "File không được tìm thấy hoặc không đúng định dạng."
                                             " Vui lòng kiểm tra lại định dạng file .xls hoặc .xlsx"))
                data = base64.decodebytes(self.field_binary_import)  # replace decodestring
                excel = xlrd.open_workbook(file_contents=data)
                sheet = excel.sheet_by_index(0)
                index = 0
                while index < sheet.nrows:
                    stt = sheet.cell(index, 0).value
                    if not self.is_number(stt):
                        index = index + 1
                        continue
                    contract_name_tmp = sheet.cell(index, 1).value
                    contract_obj = self.env['hr.contract'].search(
                        [('name', '=', contract_name_tmp), (('state', '=', 'open'))], limit=1)
                    if contract_obj.id != False:
                        contract_id = contract_obj.id
                    else:
                        raise except_orm("Cảnh báo!",
                                         (
                                                 "hợp đồng này " + str(
                                             contract_name_tmp) + 'không tồn tại hoặc chưa chạy vui lòng kiểm tra lại' + str(
                                             index + 1)
                                         )
                                         )
                    employee_code_tmp = sheet.cell(index, 2).value
                    employee_id_s = self.env['hr.employee'].search([('employee_code', '=', employee_code_tmp)], limit=1)
                    if employee_id_s.id != False:
                        employee_id = employee_id_s.id
                    else:
                        raise except_orm("Cảnh báo!",
                                         (
                                                 "Mã nhân viên " + str(
                                             employee_code_tmp) + 'có thể không tồn tại vui lòng kiểm tra lại' + str(
                                             index + 1)
                                         )
                                         )
                    date = sheet.cell(index, 3).value
                    if date:
                        start_date = datetime(*xlrd.xldate_as_tuple(date, excel.datemode))
                    contribution = sheet.cell(index, 4).value
                    if contribution > 0:
                        total_money_meal = contribution
                    else:
                        raise except_orm("Cảnh báo!",
                                         (
                                                 "Số tiền không được nhỏ hơn 0. Vui lòng kiểm tra tại dòng :" + str(
                                             index + 1)
                                         ))
                    note = sheet.cell(index, 5).value
                    line = {
                        'contract_id': contract_id,
                        'employee_id': employee_id,
                        'department_id': employee_id_s.department_id.id or None,
                        'job_id': employee_id_s.job_id.id or None,
                        'application_date': self.adjust_date,
                        'contribution_level': total_money_meal,
                        'note': note,

                    }
                    lines.append(line)
                    index = index + 1
                self.contribute_line_ids = lines
                self.field_binary_name = ''
                self.field_binary_import = None
            except ValueError as  e:
                raise osv.except_osv('Warring!', ("Có lỗi phát sinh trong quá trình import. Vui lòng kiểm tra lại."))
        else:
            raise osv.except_osv('Cảnh báo!', ("chưa có file , vui lòng chọn file import "))

class HrAdjustInsuranceContributeLine(models.Model):
    _name = 'hr.adjust.insurance.contribute.line'

    contribute_id = fields.Many2one('hr.adjust.insurance.contribute')
    contract_id = fields.Many2one('hr.contract', string='Contract Employee')
    employee_id = fields.Many2one('hr.employee', string='Employee Name')
    job_id = fields.Many2one('hr.job', "Job ")
    department_id = fields.Many2one('hr.department', "Department")
    application_date = fields.Date(string="Date Application", default=fields.Date.today)
    contribution_level = fields.Float(string="Contribution Level")
    note = fields.Char(string="Note")

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id and not self.contract_id:
            obj_hr_employee = self.env['hr.employee'].search([('id', '=', self.employee_id.id)])
            obj_contracr = self.env['hr.contract'].search(
                [('employee_id', '=', self.employee_id.id), ('state', '=', 'open')])
            if len(obj_contracr) > 0:
                self.contract_id = obj_contracr[0].id
                if obj_contracr.x_salary == 0:
                    contribution_level = obj_contracr.wage
                else:
                    contribution_level = obj_contracr.x_salary
                if len(obj_hr_employee) > 0:
                    self.contribution_level = contribution_level
                    self.job_id = obj_hr_employee.job_id.id
                    self.department_id = obj_hr_employee.department_id.id
                else:
                    raise except_orm('Lỗi', (
                            "Nhân viên này " + str(
                        obj_hr_employee.name) + " không tồn tại "))
            else:
                raise except_orm('Lỗi', (
                        "Bản ghi " + str(
                    obj_hr_employee.name) + " chưa chạy, vui lòng tạo chạy  hoặc chưa có hợp đồng cho bản ghi này "))

    @api.onchange('contract_id')
    def onchange_contract(self):
        if self.contract_id and not self.employee_id:
            if self.contract_id.state != 'open':
                raise except_orm('Lỗi', (
                        "Bản ghi " + str(
                    self.contract_id.name) + "chưa chạy vui lòng kiểm tra lại"))

            if self.contract_id.x_salary == 0:
                contribution_level = self.contract_id.wage
            else:
                contribution_level = self.contract_id.x_salary
            if self.contract_id.employee_id:
                self.employee_id = self.contract_id.employee_id.id
                self.contribution_level = contribution_level
                self.job_id = self.contract_id.employee_id.job_id.id
                self.department_id = self.contract_id.department_id.id
            else:
                raise except_orm('Lỗi', (
                        "Nhân viên này " + str(
                    self.contract_id.employee_id.name_related) + " không tồn tại "))

