# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CashPulseSettings(Document):
    pass


@frappe.whitelist()
def detect_movement_voucher_types():
    """
    اكتشاف تلقائي لأنواع المستندات التي تُنتج حركات خروج مخزون فعلية.
    يفحص آخر 90 يوماً من Stock Ledger Entry.
    يُستخدم كزر مساعدة في إعداد العميل الجديد.
    """
    rows = frappe.db.sql(
        """
        SELECT voucher_type, COUNT(*) AS cnt
        FROM `tabStock Ledger Entry`
        WHERE actual_qty < 0
        AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
        GROUP BY voucher_type
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )
    # نرجّع الأنواع التي تمثّل بيعاً فعلياً (نستبعد التسويات عادةً)
    suggestions = []
    for r in rows:
        suggestions.append({
            "voucher_type": r.get("voucher_type"),
            "movement_count": r.get("cnt"),
        })
    return suggestions
