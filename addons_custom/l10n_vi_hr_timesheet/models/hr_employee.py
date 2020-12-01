# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import timedelta
from odoo.osv import osv
import pytz
import base64
import calendar
import datetime as dt
import sys
import time
import xlrd


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_is_shift = fields.Boolean(string="Is Shift", default=False)
    x_shift_id = fields.Many2one('hr.shift', string="Shift", help="Apply for official.")