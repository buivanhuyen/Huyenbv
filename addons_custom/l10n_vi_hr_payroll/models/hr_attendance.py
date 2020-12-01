# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime, timedelta


# class HrAttendance(models.Model):
#     _inherit = "hr.attendance"
#
#     date_in = fields.Date(string="Date in", compute='_compute_worked_date', store=True, readonly=True)
#     date_out = fields.Date(string="Date out", compute='_compute_worked_date', store=True, readonly=True)
#
#     @api.depends('check_in', 'check_out')
#     def _compute_worked_date(self):
#         for attendance in self:
#             if attendance.check_out:
#                 date_out = datetime.strptime(str(attendance.check_out), '%Y-%m-%d %H:%M:%S')
#                 date_out = date_out + timedelta(hours=7)
#                 attendance.date_out = date_out.date()
#             if attendance.check_in:
#                 date_in = datetime.strptime(str(attendance.check_in), '%Y-%m-%d %H:%M:%S')
#                 date_in = date_in + timedelta(hours=7)
#                 attendance.date_in = date_in.date()


# Cap nhat cham van tay
class HrAttendanceUpdate(models.Model):
    _name = 'hr.attendance.fingerprint'

    name = fields.Char(string="Name")
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    state = fields.Selection(
        [('draft', 'Draft'), ('imported', 'Imported'), ('confirm', 'Confirm'), ('cancel', 'Cancel')], default="draft")
    lines = fields.One2many('hr.attendance.fingerprint.line', 'fingerprint_id', string="Detail")
    file_binary = fields.Binary(string="Upload File")
    file_binary_name = fields.Char()



class HrAttendanceUpdateLine(models.Model):
    _name = 'hr.attendance.fingerprint.line'

    fingerprint_id = fields.Many2one('hr.attendance.fingerprint', string="Fingerprint")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    date = fields.Date(string="Date")
    time_in = fields.Float(string="Time In")
    time_out = fields.Float(string="Time Out")
