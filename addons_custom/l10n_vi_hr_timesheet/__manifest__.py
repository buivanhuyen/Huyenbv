# -*- coding: utf-8 -*-
{
    'name': "l10n_vi_hr_timesheet",
    'summary': """
        
    """,
    'description': """
        
    """,
    'author': "",
    'website': "",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'mail', 'hr', 'hr_contract', 'hr_payroll', 'l10n_vn', 'hr_timesheet', 'hr_holidays',
                'hr_attendance',
                'hr_recruitment', 'hr_payroll_account', 'resource'],
    'data': [
        'data/hr_mail_view.xml',
        'views/hr_attendance_view.xml',
        'views/hr_shift_view.xml',
        'views/hr_resource_view.xml',
        'wizard/hr_attendance_confirmation_reason_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_timesheet_late_early_view.xml',
    ],
}
