# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.multi
    def action_approve_leader(self):
        for line in self:
            line.state = 'validate1'

    @api.multi
    def action_approve_manager(self):
        for line in self:
            line.state = 'validate'
