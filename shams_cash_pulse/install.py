# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# تهيئة بعد التركيب

import frappe


def after_install():
    """يضبط إعدادات افتراضية آمنة بعد تركيب التطبيق."""
    try:
        settings = frappe.get_single("Cash Pulse Settings")

        # أنواع حركة افتراضية إن كانت فارغة
        if not settings.sales_movement_vouchers:
            settings.append("sales_movement_vouchers", {"voucher_type": "Sales Invoice"})
            settings.append("sales_movement_vouchers", {"voucher_type": "Delivery Note"})

        if not settings.frozen_threshold_days:
            settings.frozen_threshold_days = 90
        if not settings.cogs_source:
            settings.cogs_source = "GL Account"
        if not settings.healthy_ccc_days:
            settings.healthy_ccc_days = 60
        if not settings.healthy_dso_days:
            settings.healthy_dso_days = 60
        if not settings.detail_row_limit:
            settings.detail_row_limit = 20
        settings.auto_monthly_expense = 1

        settings.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="Cash Pulse: فشل التهيئة", message=frappe.get_traceback())
