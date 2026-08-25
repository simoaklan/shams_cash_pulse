# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# دالة القراءة للداشبورد — خفيفة، تقرأ آخر snapshot فقط

import json

import frappe
from frappe.utils import flt


ALLOWED_ROLES = ("System Manager", "Accounts Manager")


@frappe.whitelist()
def get_cash_pulse_data():
    """يرجّع آخر snapshot + الاتجاه مقارنةً بالسابق."""
    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ALLOWED_ROLES):
        frappe.throw("غير مصرّح بعرض هذه البيانات")

    latest = frappe.db.sql(
        "SELECT * FROM `tabCash Pulse Snapshot` ORDER BY snapshot_date DESC LIMIT 1",
        as_dict=True,
    )

    if not latest:
        return {"empty": 1}

    snap = latest[0]

    prev = frappe.db.sql(
        """
        SELECT frozen_total, ccc_days FROM `tabCash Pulse Snapshot`
        WHERE snapshot_date < %s ORDER BY snapshot_date DESC LIMIT 1
        """,
        (snap.get("snapshot_date"),),
        as_dict=True,
    )

    trend_frozen = 0
    trend_ccc = 0
    if prev:
        trend_frozen = flt(snap.get("frozen_total")) - flt(prev[0].get("frozen_total"))
        trend_ccc = flt(snap.get("ccc_days")) - flt(prev[0].get("ccc_days"))

    # المعيار الصحي من الإعدادات (للمقارنة)
    healthy_ccc = frappe.db.get_single_value("Cash Pulse Settings", "healthy_ccc_days") or 60

    return {
        "snapshot_date": str(snap.get("snapshot_date")),
        "frozen_total": flt(snap.get("frozen_total")),
        "frozen_pct": flt(snap.get("frozen_pct")),
        "months_frozen": flt(snap.get("months_frozen")),
        "overdue_total": flt(snap.get("overdue_total")),
        "dio_days": flt(snap.get("dio_days")),
        "dso_days": flt(snap.get("dso_days")),
        "dpo_days": flt(snap.get("dpo_days")),
        "ccc_days": flt(snap.get("ccc_days")),
        "total_inventory": flt(snap.get("total_inventory")),
        "available_cash": flt(snap.get("available_cash")),
        "frozen_rows": json.loads(snap.get("frozen_rows") or "[]"),
        "overdue_rows": json.loads(snap.get("overdue_rows") or "[]"),
        "healthy_ccc_days": healthy_ccc,
        "trend_frozen": trend_frozen,
        "trend_ccc": trend_ccc,
    }


@frappe.whitelist()
def rebuild_snapshot():
    """يعيد بناء snapshot اليوم يدوياً (زر تحديث فوري)."""
    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ALLOWED_ROLES):
        frappe.throw("غير مصرّح")

    from shams_cash_pulse.cash_pulse.calculator import save_snapshot
    name = save_snapshot()
    return {"status": "ok", "snapshot": name}
