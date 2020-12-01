# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from datetime import time as datetime_time
from dateutil import relativedelta
import base64
from odoo.osv import osv

try:
    import cStringIO as stringIOModule
except ImportError:
    try:
        import StringIO as stringIOModule
    except ImportError:
        import io as stringIOModule

import xlrd
import xlwt
import babel

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    number_of_minutes = fields.Float(string="Number of Minutes")
    number_of_count = fields.Float(string="Number of Counts")


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    timesheet_id = fields.Many2one('hr.timesheet', string="Timesheet")

    @api.multi
    def _compute_details_by_salary_rule_category(self):
        for payslip in self:
            temp1 = payslip.mapped('line_ids').filtered(lambda line: line.category_id)
            temp2 = self.env['hr.payslip.line'].search(
                [('slip_id', '=', payslip.id), ('appears_on_payslip', '=', False)])
            result = temp1 | temp2
            payslip.details_by_salary_rule_category = result


    # YTI TODO To rename. This method is not really an onchange, as it is not in any view
    # employee_id and contract_id could be browse records
    @api.multi
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        # defaults
        res = {
            'value': {
                'line_ids': [],
                # delete old input lines
                'input_line_ids': [(2, x,) for x in self.input_line_ids.ids],
                # delete old worked days lines
                'worked_days_line_ids': [(2, x,) for x in self.worked_days_line_ids.ids],
                # 'details_by_salary_head':[], TODO put me back
                'name': '',
                'contract_id': False,
                'struct_id': False,
            }
        }
        if (not employee_id) or (not date_from) or (not date_to):
            return res
        date_from = str(date_from)
        date_to = str(date_to)
        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
        employee = self.env['hr.employee'].browse(employee_id)
        locale = self.env.context.get('lang') or 'en_US'
        res['value'].update({
            'name': _('Salary Slip of %s for %s') % (
                employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
            'company_id': employee.company_id.id,
        })

        if not self.env.context.get('contract'):
            # fill with the first contract of the employee
            contract_ids = self.get_contract(employee, date_from, date_to)
        else:
            if contract_id:
                # set the list of contract for which the input have to be filled
                contract_ids = [contract_id]
            else:
                # if we don't give the contract, then the input to fill should be for all current contracts of the employee
                contract_ids = self.get_contract(employee, date_from, date_to)

        if not contract_ids:
            return res
        contract = self.env['hr.contract'].browse(contract_ids[0])
        res['value'].update({
            'contract_id': contract.id
        })
        struct = contract.struct_id
        if not struct:
            return res
        res['value'].update({
            'struct_id': struct.id,
        })
        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        # TDV edit here
        for wdl in worked_days_line_ids:
            name = wdl.get('name')
            if not name:
                wdl['name'] = '-'
            code = wdl.get('code')
            if not code:
                wdl['code'] = 'X'
        if contracts:
            self.add_workdays(worked_days_line_ids, employee, date_from, date_to, contracts[0].id)

        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        # if contracts:
        #     input_temp_ids = self.add_input(contracts[0].id, date_from, date_to)
        #     for r in input_temp_ids:
        #         input_line_ids.append(r)
        res['value'].update({
            'worked_days_line_ids': worked_days_line_ids,
            'input_line_ids': input_line_ids,
        })
        return res

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):

        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return

        employee = self.employee_id
        date_from = str(self.date_from)
        date_to = str(self.date_to)
        contract_ids = []

        ttyme = datetime.fromtimestamp(time.mktime(time.strptime(date_from, "%Y-%m-%d")))
        locale = self.env.context.get('lang') or 'en_US'
        self.name = _('Salary Slip of %s for %s') % (
            employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id

        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        # TDV edit here
        for wdl in worked_days_line_ids:
            name = wdl.get('name')
            if not name:
                wdl['name'] = '-'
            code = wdl.get('code')
            if not code:
                wdl['code'] = 'X'
        if contracts:
            self.add_workdays(worked_days_line_ids, employee, date_from, date_to, contracts[0].id)
        worked_days_lines = self.worked_days_line_ids.browse([])
        for r in worked_days_line_ids:
            worked_days_lines += worked_days_lines.new(r)
        self.worked_days_line_ids = worked_days_lines

        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        input_lines = self.input_line_ids.browse([])
        # input_line_temp_ids = []
        # if contracts:
        #     input_line_temp_ids = self.add_input(contracts[0].id, date_from, date_to)
        for r in input_line_ids:
            input_lines += input_lines.new(r)
        # for r in input_line_temp_ids:
        #     input_lines += input_lines.new(r)

        self.input_line_ids = input_lines
        return

    def add_workdays(self, worked_days_line_ids, employee, date_from, date_to, contract_id):
        timesheet_id = self.timesheet_id
        if not timesheet_id:
            timesheet_id = self.env['hr.timesheet'].search(
                [('date_from', '<=', str(date_from)), ('date_to', '>=', str(date_to))],
                limit=1)
            if len(timesheet_id) == 0:
                return
        actuallies = self.env['hr.timesheet.line'].search(
            [('employee_id', '=', employee.id), ('timesheet_id', '=', timesheet_id.id)], limit=1)
        # Lay ra cau hinh di muon
        late_id = self.env['hr.timesheet.break.config'].search(
            [('active', '=', True), ('state', '=', 'active'), ('type', '=', 'late')], limit=1)
        early_id = self.env['hr.timesheet.break.config'].search(
            [('active', '=', True), ('state', '=', 'active'), ('type', '=', 'early')], limit=1)
        if len(actuallies) > 0:
            # lay ra dòng đầu tiên thể hiện số giờ làm việc chuẩn
            wk = worked_days_line_ids[0] if len(worked_days_line_ids) > 0 else []
            sequence = 0
            contract_id = contract_id
            if len(wk) > 0:
                wk['number_of_days'] = actuallies.standard_workday
                wk['name'] = "Tổng công chuẩn"
                worked_days_line_ids[0] = wk
                sequence = wk['sequence']
            # Lay ra du lieu ngay cong thuc te
            sequence = sequence + 1
            work_real = {
                'name': "Công thực tế",
                'sequence': sequence,
                'code': 'WORK_REAL',
                'number_of_days': actuallies.workday_real,
                'contract_id': contract_id
            }
            worked_days_line_ids.append(work_real)
            # Tổng giờ làm thêm
            sequence = sequence + 1
            work_real = {
                'name': "Tổng giờ làm thêm",
                'sequence': sequence,
                'code': 'ALW_OVERTIME',
                'number_of_hours': actuallies.number_of_overtime,
                'contract_id': contract_id
            }
            worked_days_line_ids.append(work_real)
            # Tổng phút đi muộn
            sequence = sequence + 1
            work_real = {
                'name': "Tổng đi muộn",
                'sequence': sequence,
                'code': 'LATE',
                'contract_id': contract_id,
                'number_of_days': actuallies.number_of_later
            }
            if late_id.id:
                if late_id.appearance == 'total':
                    work_real['name'] = 'Tổng số phút đi muộn'
                    work_real['number_of_minutes'] = actuallies.number_of_later
                    work_real['number_of_days'] = 0
                elif late_id.appearance == 'count':
                    work_real['name'] = 'Tổng số lần đi muộn'
                    work_real['number_of_count'] = actuallies.number_of_later
                    work_real['number_of_days'] = 0
                else:
                    work_real['name'] = 'Tổng đi muộn'
                    work_real['number_of_days'] = actuallies.number_of_later

            worked_days_line_ids.append(work_real)

            # Tổng phút về sớm
            sequence = sequence + 1
            work_real = {
                'name': "Tổng về sớm",
                'sequence': sequence,
                'code': 'EARLY',
                'contract_id': contract_id,
                'number_of_days': actuallies.number_of_later
            }
            if early_id.id:
                if early_id.appearance == 'total':
                    work_real['name'] = 'Tổng số phút đi muộn'
                    work_real['number_of_minutes'] = actuallies.number_of_later
                    work_real['number_of_days'] = 0
                elif early_id.appearance == 'count':
                    work_real['name'] = 'Tổng số lần đi muộn'
                    work_real['number_of_count'] = actuallies.number_of_later
                    work_real['number_of_days'] = 0
                else:
                    work_real['name'] = 'Tổng đi muộn'
                    work_real['number_of_days'] = actuallies.number_of_later
            worked_days_line_ids.append(work_real)
            # ******************************************************
            # ******************************************************
            ##### Đẩy các workeds vào worked day ######
            # ******************************************************
            # ******************************************************

    def add_input(self, contract_id, date_from, date_to):
        # TODO: Đẩy vào các input
        sequence = 0
        inputs = []

        # Hỗ trợ ăn trưa
        sequence = sequence + 1
        inputs.append({
            'name': 'Hỗ trợ ăn trưa',
            'code': 'ALW_LUNCH',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        # Hỗ trợ đi lại và liên lạc
        sequence = sequence + 1
        inputs.append({
            'name': 'Hỗ trợ đi lại, liên lạc',
            'code': 'ALW_TRAVEL_COMM',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        # Hỗ trợ nhà ở
        sequence = sequence + 1
        inputs.append({
            'name': 'Hỗ trợ nhà ở',
            'code': 'ALW_HOUSING',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        # Hỗ trợ khác
        sequence = sequence + 1
        inputs.append({
            'name': 'Hỗ trợ khác',
            'code': 'ALW_OTHER',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })

        # Tiền thưởng
        sequence = sequence + 1
        inputs.append({
            'name': 'Tiền thưởng',
            'code': 'ALW_BONUS',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        # Giảm trừ thuế TNCN
        sequence = sequence + 1
        inputs.append({
            'name': 'Thuế TNCN',
            'code': 'DED_INCOME_TAX',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })

        # Giảm trừ khác
        sequence = sequence + 1
        inputs.append({
            'name': 'Giảm trừ khác',
            'code': 'DED_OTHER',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        # Phạt đi muộn, về sớm
        sequence = sequence + 1
        inputs.append({
            'name': 'Phạt đi muộn + về sớm',
            'code': 'DED_LATER',
            'amount': 0,
            'sequence': sequence,
            'contract_id': contract_id
        })
        return inputs

    def get_income_tax(self, contract_id, timesheet_id):
        total_income = 0
        # TODO tinh luong co ban
        contract = self.env['hr.contract'].browse([contract_id])
        basic = contract.wage
        # TODO cac khoan giam tru bao hiem
        insurance = contract.x_salary
        social = insurance * contract.x_contribution_employee_social / 100
        medical = insurance * contract.x_contribution_employee_medical / 100
        unemployee = insurance * contract.x_contribution_employee_unemployment / 100
        labor = insurance * contract.x_contribution_employee_labor_accidents / 100
        # TODO cac khoan cong them tinh thue


class HrPayslipUpdateInput(models.Model):
    _name = 'hr.payslip.update.input'

    name = fields.Char(string="Name")
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    file_binary = fields.Binary(string="Upload File")
    file_binary_name = fields.Char()
    run_id = fields.Many2one('hr.payslip.run', string="Payslips Batches")
    state = fields.Selection(
        [('draft', 'Draft'), ('imported', 'Imported'), ('confirm', 'Confirm'), ('cancel', 'Cancel')], default='draft')
    lines = fields.One2many('hr.payslip.update.input.line', 'input_id', string="Details")
    structure_id = fields.Many2one('hr.payroll.structure', string="Structure")
    run_id = fields.Many2one('hr.payslip.run', string="For Payslip Batches")

    @api.onchange('run_id')
    def onchange_run(self):
        if self.run_id.id:
            self.date_from = self.run_id.date_start
            self.date_to = self.run_id.date_end

    @api.multi
    def action_generate_payslip(self):
        self.lines.unlink()
        payslip_ids = self.env['hr.payslip'].search(
            [('struct_id', '=', self.structure_id.id), ('payslip_run_id', '=', self.run_id.id)])
        result = []
        for payslip in payslip_ids:
            result.append({
                'employee_id': payslip.employee_id.id,
                'payslip_id': payslip.id,
                'result': 'Not Import'
            })
        self.lines = result

    @api.multi
    def action_download(self):
        """
        # Chuc nang download
        """

        """
        # Lay danh sach cac input
        """
        if len(self.lines) == 0:
            raise osv.except_orm("Cảnh báo!",
                                 "Khong co du lieu de tai xuong. Vui long kiem tra lai. Xin cảm ơn.")
        payslip = self.run_id.slip_ids[0]
        inputs = []
        values = []
        for input in payslip.input_line_ids:
            inputs.append(input.name + ':' + input.code)
            values.append(input.amount)

        wb = xlwt.Workbook(encoding='UTF-8')
        name_sheet = 'Bang cap nhat ket qua dau vao'
        ws = wb.add_sheet(name_sheet)
        ws.protect = True
        ws.password = 'doanvanthien@devpro.com'
        editable = xlwt.easyxf("protection: cell_locked false;")
        read_only = xlwt.easyxf("")

        style_content = xlwt.easyxf(
            "align: horiz center;font:bold True;borders: top thin,right thin,bottom thin,left thin")
        style_head_po = xlwt.easyxf(
            'align: horiz center;font:bold True;pattern: pattern solid;borders: top thin,right thin,bottom thin,left thin')
        style_body = xlwt.easyxf('borders:top thin,right thin,bottom thin,left thin')
        style = xlwt.XFStyle()
        style.alignment.wrap = 1

        ws.col(0).width = 20 * 100
        ws.write(0, 0, u'STT', read_only)
        ws.col(1).width = 10 * 500
        ws.write(0, 1, u'Ma nhan vien', read_only)
        ws.col(2).width = 10 * 367
        ws.write(0, 2, u'Ten nhan vien', read_only)
        index = 3
        for input in inputs:
            ws.col(index).width = 10 * 500
            ws.write(0, index, input, read_only)
            index += 1

        index = 1
        for line in self.lines:
            if not line.employee_id.x_code:
                raise osv.except_orm("Cảnh báo!",
                                     "Vui lòng cập nhật mã nhân viên cho người lao động " + str(
                                         line.employee_id.name) + " trước khi tiến hành tải về. Xin cảm ơn.")

            ws.write(index, 0, str(index), read_only)
            ws.write(index, 1, line.employee_id.x_code, read_only)
            ws.write(index, 2, line.employee_id.name, read_only)
            row = 3
            t_index = 0
            for input in inputs:
                ws.write(index, row, values[t_index], editable)
                row += 1
                t_index += 1

            index = index + 1

        file_io = stringIOModule.BytesIO()
        wb.save(file_io)
        xls = file_io.getvalue()

        vals = {
            'name': 'hr.payslip.update.input.xls',
            'datas': base64.b64encode(xls),
            'datas_fname': 'hr.payslip.update.input.xls',
            'type': 'binary',
            'res_model': 'hr.payslip.update.input',
            # 'res_id': self.id,
        }
        file_xls = self.env['ir.attachment'].create(vals)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/' + str(file_xls.id) + '?download=true',
            'target': 'new',
        }

    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def check_format_file_excel(self, file_name):
        if file_name == False:
            raise osv.except_osv('Cảnh Báo!', 'Vui lòng kiểm tra lại tên của file trước khi đưa vào hệ thống.')
        if file_name.endswith('.xls') == False and file_name.endswith('.xlsx') == False:
            self.file_binary = None
            self.file_binary_name = None
            raise osv.except_osv("Cảnh báo!",
                                 ("Định dạng file không đúng. Vui lòng đẩy file excel với định dạng: .xlsx or .xls"))

    @api.multi
    def action_import(self, context=None):
        """ kiểm tra file có rỗng """
        if self.file_binary is None:
            raise osv.except_orm('Cảnh báo', 'Vui lòng lựa chọn file trước khi import. Xin cảm ơn')
        """ Kiểm tra định dạng file """
        self.check_format_file_excel(self.file_binary_name)
        """ tiến hành đọc file """
        file_import = self.file_binary
        data = base64.decodebytes(file_import)
        excel = xlrd.open_workbook(file_contents=data)
        sheet = excel.sheet_by_index(0)
        index = 1
        employee_obj = self.env['hr.employee']
        # Lay danh sach column va danh sach input
        inputs = []
        index_col = 3
        indexs = []
        while index_col < sheet.ncols:
            value = sheet.cell(0, index_col).value
            value = str(value)
            list_value = value.split(':')
            if len(list_value) > 0:
                inputs.append(list_value[len(list_value) - 1])
                indexs.append(index_col)
            else:
                raise osv.except_orm('Cảnh báo', 'File không đúng định dạng. Vui lòng kiểm tra lại. Xin cảm ơn.')
            index_col += 1
        if len(inputs) == 0:
            raise osv.except_orm('Cảnh báo', 'File không đúng định dạng. Vui lòng kiểm tra lại. Xin cảm ơn.')

        while index < sheet.nrows:
            employee_code = sheet.cell(index, 1).value
            if self.is_number(employee_code):
                employee_code = str(int(employee_code))
            employee_id = employee_obj.search([('x_code', '=', employee_code)])
            if len(employee_id) == 0:
                raise osv.except_orm("Cảnh báo!",
                                     "Không tìm thấy nhân viên có mã " + str(employee_code) + " tại dòng " + str(index))
            input_line_id = self.env['hr.payslip.update.input.line'].search([('employee_id', '=', employee_id.id)],
                                                                            limit=1)
            if len(input_line_id) == 0:
                raise osv.except_orm('Cảnh báo', 'Mã nhân viên ' + str(
                    employee_code) + ' không được tìm thấy trong chi tiết cập nhật input. Vui lòng kiểm tra lại. Xin cảm ơn.')
            payslip_id = input_line_id.payslip_id
            temp_col = 0
            result_str = ""
            for input in inputs:
                value = sheet.cell(index, indexs[temp_col]).value
                col_str = sheet.cell(0, indexs[temp_col])
                temp_col += 1
                if self.is_number(value) == False:
                    raise osv.except_orm('Cảnh báo', 'Giá trị không đúng định dạng số tại dòng số ' + str(
                        index) + '. Vui lòng kiểm tra lại. Xin cảm ơn.')
                input_id = self.env['hr.payslip.input'].search(
                    [('payslip_id', '=', payslip_id.id), ('code', '=', input)], limit=1)
                if len(input_id) == 0:
                    continue
                if value == 0:
                    continue
                # input_id.amount = value
                result_str += str(input) + ': ' + str(value) + '\n'
            input_line_id.result = result_str
            index = index + 1
        self.file_binary = None
        self.file_binary_name = None
        self.state = 'imported'

    @api.multi
    def action_confirm(self):
        for line in self.lines:
            payslip_id = line.payslip_id
            result = line.result
            values = result.split('\n')
            for value in values:
                temp_values = value.split(':')
                if len(temp_values) == 2:
                    code = temp_values[0]
                    amount = temp_values[1]
                    input_id = self.env['hr.payslip.input'].search(
                        [('payslip_id', '=', payslip_id.id), ('code', '=', code)], limit=1)
                    if len(input_id) == 0:
                        continue

                    input_id.amount = amount
        self.state = 'confirm'

    @api.multi
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise osv.except_orm('Cảnh báo',
                                     'Không thể xóa bản ghi khi đang ở trạng thái khác Dự thảo. Vui lòng kiểm tra lại. Xin cảm ơn.')
        return super(HrPayslipUpdateInput, self).unlink()


class HrPayslipUpdateInputLine(models.Model):
    _name = 'hr.payslip.update.input.line'

    input_id = fields.Many2one('hr.payslip.update.input', string="Input")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip")
    result = fields.Text(string="Result")



class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def get_accounts(self):
        return self.env['account.account'].search([('code', '=like', '334%')]).ids

    def _get_partner_id(self, credit_account):
        """
        Get partner_id of slip line to use in account_move_line
        """
        # use partner of salary rule or fallback on employee's address
        res = super(HrPayslipLine, self)._get_partner_id(credit_account)
        partner_id = self.slip_id.employee_id.address_home_id.id
        account_ids = self.get_accounts()
        if self.salary_rule_id.account_credit.id in account_ids and res != partner_id and credit_account:
            if not partner_id:
                raise osv.except_orm("Cảnh báo!",
                               "Vui lòng báo lại quản trị viên cấu hình Đối tác (Private Address) trong Thông tin Liên hệ của Nhân viên " + str(
                                   self.employee_id.name) + ". Xin cảm ơn.")
            else:
                return partner_id
        return res

