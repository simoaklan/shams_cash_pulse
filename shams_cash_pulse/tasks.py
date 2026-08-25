# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# المهام المجدولة

import frappe

from shams_cash_pulse.cash_pulse.calculator import save_snapshot


def build_daily_snapshot():
    """تُستدعى يومياً عبر scheduler. تبني snapshot جديد."""
    try:
        name = save_snapshot()
        frappe.logger().info("Cash Pulse: snapshot يومي تم بناؤه: {0}".format(name))
    except Exception:
        frappe.log_error(
            title="Cash Pulse: فشل بناء snapshot اليومي",
            message=frappe.get_traceback(),
        )
