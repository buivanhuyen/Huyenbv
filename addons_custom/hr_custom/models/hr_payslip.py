# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime
from datetime import time
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


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    timesheet_id = fields.Many2one('hr.timesheet', string="Timesheet")
    timesheet_line_id = fields.Many2one('hr.timesheet.line', string="Timesheet Line")
    payroll_line_id = fields.Many2one('hr.payroll.line', string="Payroll Line")
    payroll_id = fields.Many2one('hr.payroll', string="Payroll")

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
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
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
        input_line_ids = self.get_inputs(contracts, date_from, date_to)
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
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
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
        worked_days_lines = self.worked_days_line_ids.browse([])
        for r in worked_days_line_ids:
            worked_days_lines += worked_days_lines.new(r)
        self.worked_days_line_ids = worked_days_lines

        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        input_lines = self.input_line_ids.browse([])
        for r in input_line_ids:
            input_lines += input_lines.new(r)
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
