from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError, except_orm, Warning
from odoo.osv import osv


class HrGlobalLeaves(models.Model):
    _name = 'hr.global.leaves'
    _description = "Global Leaves"

    name = fields.Char(string="Name")
    date_from = fields.Datetime(string="Date From")
    date_to = fields.Datetime(string="Date To")
    description = fields.Text(string="Description")
