# -*- coding: utf-8 -*-
{
    'name': "HR Customize",
    'summary': """
    HR Customize
    """,
    'description': """
        HR Customize
    """,
    'author': "",
    'website': "",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'hr', 'l10n_vi_hr_payroll', 'l10n_vi_hr_timesheet', 'hr_timesheet', 'hr_contract', 'resource',
                'hr_holidays', 'hr_payroll'],
    'data': [
        'data/hr_payroll_data.xml',
        'data/hr_payslip_data.xml',
        'data/approve.xml',
        'views/hr_contract_view.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_management_lunch_view.xml',
        'views/hr_register_overtime_view.xml',
        'views/hr_global_leaves_view.xml',
        'views/hr_management_constructor_view.xml',
        'views/hr_timesheet_view.xml',
        'wizard/hr_timesheet_generate_employee_view.xml',
        # 'security/ir.model.access.csv',
        'views/hr_payroll_view.xml',
        # 'views/report_payroll_pdf.xml',
        'views/hr_payroll_line_view.xml',
        'views/hr_leave_view.xml',
        'views/hr_constructor_view.xml',
        # 'views/hr_employee_view.xml',
    ],
}
