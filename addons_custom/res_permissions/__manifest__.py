# -*- coding: utf-8 -*-
{
    'name': "res_permissions",

    'summary': """
        """,

    'description': """
        Long description of module's purpose
    """,

    'author': "HuyenBV",
    'website': "",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/group_emplpoyee.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/hr_leave_views.xml',
        'views/hr_timesheet_view.xml',
        'views/hr_payroll_views.xml',
        'views/hr_attendance_views.xml',
        # 'security/ir_rule_employee.xml',
    ],
    # only loaded in demonstration mode
}