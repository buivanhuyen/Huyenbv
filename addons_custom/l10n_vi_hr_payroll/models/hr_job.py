# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HrJob(models.Model):
    _inherit = 'hr.job'

    x_code = fields.Char(string='Job code')

    @api.multi
    def name_get(self):
        res = []
        for job in self:
            code = job.x_code or '-'
            res.append((job.id, '[' + code + '] ' + job.name))
        return res