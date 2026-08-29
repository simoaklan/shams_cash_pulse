# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PurchaseForecastSettings(Document):
    pass


@frappe.whitelist()
def detect_entry_types():
    """
    اكتشاف تلقائي لأنواع Stock Entry الخارجة — يساعد المُركِّب على التمييز
    بين البيع الحقيقي (عملاء) والاستبعاد (مؤثرين، تحويلات).
    """
    rows = frappe.db.sql(
        """
        SELECT se.stock_entry_type, COUNT(*) AS cnt,
               SUM(ABS(sle.actual_qty)) AS qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabStock Entry` se ON se.name = sle.voucher_no
        WHERE sle.voucher_type = 'Stock Entry'
        AND sle.actual_qty < 0
        AND se.docstatus = 1
        AND sle.posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
        GROUP BY se.stock_entry_type
        ORDER BY cnt DESC
        """,
        as_dict=True,
    )
    return rows
