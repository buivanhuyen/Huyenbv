# -*- coding: utf-8 -*-
from odoo import http
import logging
from odoo.exceptions import except_orm
import odoo.addons.web.controllers.main as base_main
_logger = logging.getLogger(__name__)


class DataSet(base_main.DataSet):
    """
        Các model không phân quyền được bằng record rule thì phân quyền ở đây.
    """
    def do_search_read(self, model, fields=False, offset=0, limit=False, domain=None, sort=None, context=None):
        uid = http.request.env.uid
        cr = http.request.cr
        UserObj = http.request.env['res.users']

        EmployeeObj = http.request.env['hr.employee']
        user = UserObj.sudo().search([('id', '=', uid)], limit=1)
        if uid != 1:
            if model == 'hr.attendance':
                if not (uid == 1):
                    group_employee = UserObj.has_group('res_permissions.group_employee')
                    group_leader_employee = UserObj.has_group('res_permissions.group_leader_employee')
                    group_manager_employee = UserObj.has_group('res_permissions.group_manager_employee')
                    group_manager_all = UserObj.has_group('res_permissions.group_manager_all')
                    if group_manager_employee or group_manager_all:
                        employee_ids = EmployeeObj.search([('active', '=', True)])
                        domain += [('employee_id', 'in', employee_ids.ids)]

                    elif group_leader_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', uid)])
                        if not employee_uid:
                            raise except_orm('Bạn chưa cấu hình user cho nhân viên')
                        employee_ids = EmployeeObj.search(
                            [('department_id', '=', employee_uid.department_id.id), ('active', '=', True)])
                        if employee_uid:
                            domain += [('employee_id', '=', employee_ids.ids)]
                        else:
                            domain += [['id', '=', 0]]
                    elif group_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', user.id), ('active', '=', True)])
                        if not employee_uid:
                            raise except_orm('Bạn chưa cấu hình user cho nhân viên')
                        domain += [('employee_id', '=', employee_uid.id)]

                    else:
                        domain+=[['id', '=', 0]]

            if model == 'hr.contract':
                if not (uid == 1):
                    group_employee = UserObj.has_group('res_permissions.group_employee')
                    group_leader_employee = UserObj.has_group('res_permissions.group_leader_employee')
                    group_manager_employee = UserObj.has_group('res_permissions.group_manager_employee')
                    if group_manager_employee:
                        employee_ids = EmployeeObj.search([('active', '=', True)])
                        domain += [('employee_id', 'in', employee_ids.ids)]

                    elif group_employee or group_leader_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', user.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_uid.id)]

                    else:
                        domain += [['id', '=', 0]]

            if model == 'hr.register.overtime':
                if not (uid == 1):
                    group_employee = UserObj.has_group('res_permissions.group_employee')
                    group_leader_employee = UserObj.has_group('res_permissions.group_leader_employee')
                    group_manager_employee = UserObj.has_group('res_permissions.group_manager_employee')
                    group_manager_all = UserObj.has_group('res_permissions.group_manager_all')
                    if group_manager_employee or group_manager_all:
                        employee_ids = EmployeeObj.search([('active', '=', True)])
                        domain += [('employee_id', 'in', employee_ids.ids)]

                    elif group_leader_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', uid)])
                        employee_ids = EmployeeObj.search(
                            [('department_id', '=', employee_uid.department_id.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_ids.ids)]

                    elif group_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', user.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_uid.id)]

                    else:
                        domain+=[['id', '=', 0]]

            if model == 'hr.leave':
                if not (uid == 1):
                    group_employee = UserObj.has_group('res_permissions.group_employee')
                    group_leader_employee = UserObj.has_group('res_permissions.group_leader_employee')
                    group_manager_employee = UserObj.has_group('res_permissions.group_manager_employee')
                    group_manager_all = UserObj.has_group('res_permissions.group_manager_all')
                    if group_manager_employee or group_manager_all:
                        employee_ids = EmployeeObj.search([('active', '=', True)])
                        domain += [('employee_id', 'in', employee_ids.ids)]

                    elif group_leader_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', uid)])
                        employee_ids = EmployeeObj.search(
                            [('department_id', '=', employee_uid.department_id.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_ids.ids)]

                    elif group_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', user.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_uid.id)]

                    else:
                        domain+=[['id', '=', 0]]

            if model == 'hr.constructor':
                if not (uid == 1):
                    group_employee = UserObj.has_group('res_permissions.group_employee')
                    group_leader_employee = UserObj.has_group('res_permissions.group_leader_employee')
                    group_manager_employee = UserObj.has_group('res_permissions.group_manager_employee')
                    group_manager_all = UserObj.has_group('res_permissions.group_manager_all')
                    if group_manager_employee or group_manager_all:
                        employee_ids = EmployeeObj.search([('active', '=', True)])
                        domain += [('employee_id', 'in', employee_ids.ids)]

                    elif group_leader_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', uid)])
                        employee_ids = EmployeeObj.search(
                            [('department_id', '=', employee_uid.department_id.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_ids.ids)]

                    elif group_employee:
                        employee_uid = EmployeeObj.search([('user_id', '=', user.id), ('active', '=', True)])
                        domain += [('employee_id', '=', employee_uid.id)]

                    else:
                        domain+=[['id', '=', 0]]
        return super(DataSet, self).do_search_read(model, fields, offset, limit, domain, sort)


