# -*- coding: utf-8 -*-
from odoo import http, api
import json
import logging
from xmlrpc import client as xmlrpclib
import base64
from datetime import datetime

CODE_OK = 1
CODE_PARAM_NOT_PROVIDED = 1001
CODE_PARAM_INVALID = 1002
CODE_SYSTEM_ERROR = 1003
CODE_ACCESS_TOKEN_INVALID = 1004
CODE_PHONE_NUMBER_ALREADY_EXISTS = 1005
CODE_EMAIL_ALREADY_EXISTS = 1006

ERROR_UNAUTHORIZED = 401
ERROR_FORBIDDEN = 403
ERROR_NOT_FOUND = 404
ERROR_CONFLICT = 409
ERROR_ECODE = 410
ERROR = 0  # Các lỗi trả về 0

ACCESS_TOKEN_LENGTH = 64

API_URL_PREFIX = '/controller'
CODE_WAREHOUSE = 'WHM'
CODE_BRANCH = 'THN'
_logger = logging.getLogger(__name__)


class ApiException(Exception):
    def __init__(self, message, code=0):
        self.message = message
        self.code = code


class HttpController(http.Controller):
    def dispatch_request(self, action, **kw):
        try:
            r = None
            if action == 'update_revenue_when_change_journal_recognition':
                r = self.do_update_revenue_when_change_journal_recognition()
            if r is not None:
                response_obj = {"code": 1, "data": r}
                return [response_obj]
            else:
                raise ApiException("It seems to be no action was specified", ERROR_FORBIDDEN)
        except xmlrpclib.Fault as e:
            response_object = {'code': CODE_SYSTEM_ERROR, 'message': e.faultString}
            _logger.error(e)
            return response_object
        except ApiException as e:
            response_object = {'code': e.code, 'message': e.message}
            _logger.error(e)
            return [response_object]

    def do_update_revenue_when_change_journal_recognition(self):
        cr = http.request.cr
        params = http.request.jsonrequest
        UsersObj = http.request.env['res.users']
        order_ids = []

        query_get_order_have_debt = '''
            SELECT
            a.id
            , b.amount amount_debt
            FROM pos_order a
            LEFT JOIN account_bank_statement_line b ON a.id = b.pos_statement_id
            LEFT JOIN account_journal c ON b.journal_id = c.id
            WHERE c.code = 'GN'
            AND a.session_id <> 1
        '''
        cr.execute(query_get_order_have_debt, ())
        res = cr.dictfetchall()
        if res:
            for r in res:
                order = http.request.env['pos.order'].sudo().search([('id', '=', r['id'])])
                if not order: raise ApiException("Không tìm thấy order có id %s" % (str(r['id'])), ERROR)
                order.sudo().write({
                    'x_total_order': order.x_total_order + r['amount_debt']
                })
                order.sudo().partner_id.write({
                    'x_loyal_total': order.partner_id.x_loyal_total + r['amount_debt']
                })
                # if order.x_allocation_ids:
                #     for allocation in order.x_allocation_ids:
                query_delete_revenue_allocation = """
                    DELETE FROM pos_revenue_allocation WHERE order_id = %s
                """
                cr.execute(query_delete_revenue_allocation, (order.id, ))
                if order.x_user_id:
                    order.sudo()._auto_allocation()
                if order.x_allocation_ids:
                    for allocation in order.x_allocation_ids:
                        query_update_allocation = """
                            UPDATE pos_revenue_allocation SET create_uid = %s, write_uid = %s, date = %s WHERE id = %s
                        """
                        cr.execute(query_update_allocation, (order.create_uid.id, order.write_uid.id, order.date_order, allocation.id))
                        # allocation.sudo().write({
                        #     'create_uid': order.create_uid,
                        #     'write_uid': order.write_uid,
                        #     'date': order.date_order,
                        # })
            return {"message": "Cập nhật thành công"}

    @http.route(route=API_URL_PREFIX + '/update_revenue_when_change_journal_recognition', type='json', auth='public', methods=['POST'], website=True)
    def purchase_order(self, **kwargs):
        return self.dispatch_request('update_revenue_when_change_journal_recognition')
