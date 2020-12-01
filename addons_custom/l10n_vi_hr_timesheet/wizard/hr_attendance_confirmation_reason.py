from odoo import models, fields, api, _
from odoo.exceptions import UserError, except_orm
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import threading

class HrAttendanceConfirmationReason(models.TransientModel):
    _name = 'hr.attendance.confirmation.reason'

    attendance_id = fields.Many2one('hr.attendance', string='Attendance')
    reason = fields.Char(string="Reason")
    type = fields.Selection([('agree', 'Agree'), ('degree', 'Degree')], string="Type")

    @api.multi
    def action_confirm(self):
        if self.type == 'agree':
            self.attendance_id.write({
                'result_timekeeping': 'agree',
                'reason_confirm': str(
                    self.attendance_id.reason_confirm) + " . \n " + str(
                    self.reason) if self.attendance_id.reason_confirm else "" + str(
                    self.reason)
            })
            email_hr = self.env['ir.config_parameter'].sudo().get_param(
                'email_hr', 'False')
            list_email_hr = email_hr.split(',')
            for email in list_email_hr:
                hr_partner_id = self.env['res.partner'].search([('active', '=', True), ('email', '=', email)])
                if hr_partner_id:
                    hr_mail = self.env['izi.sent.mail.template'].create({
                        'name': 'Đơn chấm công của' + ' ' + str(self.attendance_id.employee_id.name) + '.',
                        'model': 'hr.attendance',
                        'res_id': self.attendance_id.id,
                        'partner_id': hr_partner_id.id,
                        'content_before': 'Đơn chấm công của' + ' ' + str(self.attendance_id.employee_id.name) + '.',
                        'content': 'Kết quả chấm công:Chưa phê duyệt -> Được duyệt',
                        'content_after': 'Để xem chi tiết, bạn vui lòng click chọn vào button dưới đây. Xin cảm ơn.'
                    })
                    thread_var = threading.Thread(target=hr_mail.action_send_mail_major(True, True))
                    thread_var.start()
        else:
            self.attendance_id.write({
                'result_timekeeping': 'degree',
                'reason_confirm': str(
                    self.attendance_id.reason_confirm) + " . \n " + str(
                    self.reason) if self.attendance_id.reason_confirm else "" + str(
                    self.reason)
            })
        return {'type': 'ir.actions.act_window_close'}
