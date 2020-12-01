# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import datetime
from datetime import date as t_date
from datetime import datetime as t_datetime, timedelta
from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError
import os, sys, subprocess, csv
import pytz
import shutil
# import numpy


class SentMailTemplate(models.TransientModel):
    _name = 'izi.sent.mail.template'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char(string="Model Name", required=1)
    model = fields.Char(string='Model', required=1)
    res_id = fields.Integer(string="ID Document", required=1)
    partner_id = fields.Many2one('res.partner', string="Partner", required=1)
    content = fields.Char(string="Content", required=1)
    content_before = fields.Char(string="Content Before", required=1)
    content_after = fields.Char(string="Content After", required=1)

    def action_send_mail_major(self, body=True, partner=True):
        partner = self.partner_id
        partner_id = partner.id
        url = self.get_url(self.model, self.res_id)
        body = self.get_body(partner.name, self.content, url, 'Xem', self.content_before, self.content_after)
        subtype_id = self.env['ir.model.data'].search(
            [('model', '=', 'mail.message.subtype'), ('name', '=', 'mt_comment'), ('module', '=', 'mail')], limit=1)
        kwargs = {
            'composition_mode': 'mass_mail',
            'partner_ids': [(4, partner_id)],
            'auto_delete': False,
            'auto_delete_message': False,
            'parent_id': False,
            'subtype_id': subtype_id.res_id,
            'body': body.encode('utf-8')
        }
        self.message_post_with_template(template_id=False, **kwargs)

    def get_body(self, name, model, url, button_name, content_before=True, content_after=True):
        body = ''
        body = '\b<p>Dear ' + str(name) + ' </p> \n' \
                                          '<p>\n ' + str(content_before) + ' <span style="color: red">' + str(
            model) + '</span> ' + str(
            content_after) + ' </p> \n' \
                             '<p><a style="background-color: #9E588B; margin-top: 10px; padding: 10px; text-decoration: none; color: #fff; border-radius: 5px; font-size: 16px; font-weight: bold;" href="' + str(
            url) + '"> \n' + str(button_name) + '\n </a> </p> \n' \
                                                '<p style="color:#9E588B;">Powered by <a target="_blank" href="http://www.erpviet.vn">ERPViet</a>.</p>\n'
        return body

    def get_url(self, model, res_id):
        url = ''
        action = self.env['ir.actions.act_window'].search([('res_model', '=', str(model))], limit=1)
        if len(action) == 0:
            url = '/mail/view?model=' + str(model) + '&res_id=' + str(res_id)
        else:
            url = '/mail/view?model=' + str(model) + '&res_id=' + str(res_id) + '&action=' + str(action.id)
        return url
