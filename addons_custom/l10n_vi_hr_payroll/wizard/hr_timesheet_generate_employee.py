from odoo import models, fields, api, _
from odoo.exceptions import UserError, except_orm
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HrTimesheetGenerateEmployee(models.TransientModel):
    _name = 'hr.timesheet.generate.employee'

    employee_ids = fields.Many2many('hr.employee', 'hr_employee_timesheet_generate_group_rel', 'timesheet_id',
                                    'employee_id',
                                    'Employees')
    timesheet_id = fields.Many2one('hr.timesheet', string="Timesheet")

    @api.multi
    def compute_sheet(self):
        if len(self.employee_ids) > 0:
            for employee in self.employee_ids:
                if self.timesheet_id.id:
                    timesheet_line = self.env['hr.timesheet.line'].search(
                        [('employee_id', '=', employee.id), ('timesheet_id', '=', self.timesheet_id.id)])
                    if len(timesheet_line) == 0:
                        timesheet_line = self.env['hr.timesheet.line'].create({
                            'employee_id': employee.id,
                            'department_id': employee.department_id.id,
                        })

        return {'type': 'ir.actions.act_window_close'}
