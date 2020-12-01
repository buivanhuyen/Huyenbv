# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrDepartmentCustom(models.Model):
    _inherit = 'hr.department'

    x_code = fields.Char(string='Department code')
    x_notes = fields.Text(help="Write Note")


    @api.model
    def create(self, vals):
        res = super(HrDepartmentCustom, self).create(vals)
        for item in res:
            if item.manager_id.user_id:
                item.manager_id.user_id.x_department_id = item.id
        return res

    @api.one
    def write(self, vals):
        res = super(HrDepartmentCustom, self).write(vals)
        if vals.get('manager_id'):
            if self.manager_id.user_id:
                self.manager_id.user_id.x_department_id = self.id
        return res

