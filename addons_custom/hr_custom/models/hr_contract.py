# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime


class HrContract(models.Model):
    _inherit = "hr.contract"

    x_allowance_fix = fields.Float(string="Allowance Fix")
    x_allowance_other = fields.Float(string="Allowance Other")
    x_allowance_diligence = fields.Float(string="Allowance Diligence")
    x_allowance_dwelling_house = fields.Float(string="Allowance Dwelling House")
    x_allowance_telephone = fields.Float(string="Allowance Telephone")
    x_allowance_responsibility = fields.Float(string="Allowance Responsibility")
    x_allowance_travel = fields.Float(string="Allowance Travel")
    x_allowance_technique = fields.Float(string="Allowance Technique")
    x_allowance_toxic = fields.Float(string="Allowance Toxic")
    x_ratio_travel = fields.Float(string="Ratio for Allowance Travel")
    x_ratio_toxic = fields.Float(string="Ratio for Allowance Toxic")