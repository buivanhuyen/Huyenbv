from odoo import models, fields, api, _
from odoo.exceptions import UserError,except_orm
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT



class hr_adjust_contribute_by_employees(models.TransientModel):
    _name = 'hr.insurance.employees'

    employee_ids = fields.Many2many('hr.employee', 'hr_employee_insurance_group_rel', 'insurance_id', 'employee_id',
                                    'Employees')
    contribute_id = fields.Many2one('hr.adjust.insurance.contribute', string="Contribute")

    @api.multi
    def compute_sheet(self):
        contribute_line_pool = self.env['hr.adjust.insurance.contribute.line']
        if len(self.employee_ids) > 0:
            for emp in self.employee_ids:
                contribute_id_line = contribute_line_pool.search(
                    [('contribute_id', '=', self.contribute_id.id), ('employee_id.id', '=', emp.id)])
                if contribute_id_line:
                    raise except_orm("Lỗi", (" Nhân viên " + str(
                        emp.name) + " đã tồn tại"))

                else:
                    obj_contracr = self.env['hr.contract'].search(
                        [('employee_id', '=', emp.id), ('state', '=', 'open')])
                    if len(obj_contracr) > 0:
                        if obj_contracr.x_salary == 0:
                            contribution_level = obj_contracr.wage
                        else:
                            contribution_level = obj_contracr.x_salary
                        res = {
                            'contract_id': obj_contracr[0].id,
                            'contribute_id': self.contribute_id.id,
                            'employee_id': emp.id,
                            'job_id': emp.job_id.id,
                            'department_id': emp.department_id.id,
                            'application_date': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'contribution_level': contribution_level,
                            'note': False
                        }
                        contribute_line_pool.create(res)
                    else:
                        raise except_orm('Lỗi', (
                                "Nhân viên" + str(
                            emp.name_related) + " chưa được tạo hợp đồng, vui lòng tạo hợp đồng cho nhân viên này "))
        return {'type': 'ir.actions.act_window_close'}