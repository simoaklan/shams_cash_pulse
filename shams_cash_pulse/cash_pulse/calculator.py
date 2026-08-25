# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# منطق حساب مؤشرات نبض النقد — Python كامل (لا قيود RestrictedPython)

import json

import frappe
from frappe.utils import flt, nowdate


DEFAULT_VOUCHER_TYPES = ["Sales Invoice", "Delivery Note"]


def get_settings():
    """يجلب الإعدادات مع قيم افتراضية آمنة إن لم تُضبط."""
    settings = frappe.get_single("Cash Pulse Settings")

    voucher_types = [r.voucher_type for r in settings.sales_movement_vouchers if r.voucher_type]
    if not voucher_types:
        voucher_types = DEFAULT_VOUCHER_TYPES

    excluded_accounts = [r.account for r in settings.excluded_cash_accounts if r.account]

    return {
        "voucher_types": voucher_types,
        "frozen_threshold_days": settings.frozen_threshold_days or 90,
        "cogs_source": settings.cogs_source or "GL Account",
        "cogs_account": settings.cogs_account,
        "excluded_accounts": excluded_accounts,
        "auto_monthly_expense": settings.auto_monthly_expense,
        "manual_monthly_expense": flt(settings.manual_monthly_expense),
        "healthy_ccc_days": settings.healthy_ccc_days or 60,
        "detail_row_limit": settings.detail_row_limit or 20,
    }


def compute_snapshot():
    """
    يحسب كل المؤشرات ويرجّع قاموساً جاهزاً للحفظ في Cash Pulse Snapshot.
    """
    cfg = get_settings()
    voucher_types = cfg["voucher_types"]
    threshold = cfg["frozen_threshold_days"]
    limit = cfg["detail_row_limit"]

    placeholders = ", ".join(["%s"] * len(voucher_types))

    # ===== إجمالي المخزون =====
    total_inventory = flt(frappe.db.sql(
        "SELECT SUM(actual_qty * valuation_rate) FROM `tabBin` WHERE actual_qty > 0"
    )[0][0])

    # ===== COGS =====
    annual_cogs = _compute_cogs(cfg)

    # ===== DIO =====
    dio_days = (total_inventory / annual_cogs) * 365 if annual_cogs > 0 else 0

    # ===== النقد المجمّد =====
    frozen_subquery = """
        SELECT DISTINCT sle.item_code FROM `tabStock Ledger Entry` sle
        WHERE sle.voucher_type IN ({ph})
        AND sle.actual_qty < 0
        AND sle.posting_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    """.format(ph=placeholders)

    frozen_total = flt(frappe.db.sql(
        """
        SELECT SUM(b.actual_qty * b.valuation_rate)
        FROM `tabBin` b
        WHERE b.actual_qty > 0
        AND b.item_code NOT IN ({subq})
        """.format(subq=frozen_subquery),
        tuple(voucher_types) + (threshold,),
    )[0][0])

    frozen_pct = (frozen_total / total_inventory) * 100 if total_inventory > 0 else 0

    frozen_rows = frappe.db.sql(
        """
        SELECT b.item_code, b.actual_qty, b.valuation_rate,
               (b.actual_qty * b.valuation_rate) AS frozen_value
        FROM `tabBin` b
        WHERE b.actual_qty > 0
        AND b.item_code NOT IN ({subq})
        ORDER BY frozen_value DESC LIMIT %s
        """.format(subq=frozen_subquery),
        tuple(voucher_types) + (threshold, limit),
        as_dict=True,
    )

    # ===== DSO =====
    total_ar = flt(frappe.db.sql(
        "SELECT SUM(outstanding_amount) FROM `tabSales Invoice` WHERE docstatus = 1 AND outstanding_amount > 0"
    )[0][0])

    annual_sales = flt(frappe.db.sql(
        """
        SELECT SUM(grand_total) FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
        """
    )[0][0])

    dso_days = (total_ar / annual_sales) * 365 if annual_sales > 0 else 0

    # ===== الذمم المتأخرة =====
    overdue_total = flt(frappe.db.sql(
        """
        SELECT SUM(outstanding_amount) FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE()
        """
    )[0][0])

    overdue_rows = frappe.db.sql(
        """
        SELECT customer, SUM(outstanding_amount) AS overdue_amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE()
        GROUP BY customer ORDER BY overdue_amount DESC LIMIT %s
        """,
        (limit,),
        as_dict=True,
    )

    # ===== DPO =====
    total_ap = flt(frappe.db.sql(
        "SELECT SUM(outstanding_amount) FROM `tabPurchase Invoice` WHERE docstatus = 1 AND outstanding_amount > 0"
    )[0][0])

    annual_purchases = flt(frappe.db.sql(
        """
        SELECT SUM(grand_total) FROM `tabPurchase Invoice`
        WHERE docstatus = 1 AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
        """
    )[0][0])

    dpo_days = (total_ap / annual_purchases) * 365 if annual_purchases > 0 else 0

    # ===== CCC =====
    ccc_days = dio_days + dso_days - dpo_days

    # ===== النقد المتاح =====
    available_cash = _compute_available_cash(cfg)

    # ===== المصروف الشهري + التأطير =====
    monthly_expense = _compute_monthly_expense(cfg)
    months_frozen = frozen_total / monthly_expense if monthly_expense > 0 else 0

    return {
        "snapshot_date": nowdate(),
        "frozen_total": frozen_total,
        "frozen_pct": frozen_pct,
        "months_frozen": months_frozen,
        "overdue_total": overdue_total,
        "under_priced_count": 0,
        "dio_days": dio_days,
        "dso_days": dso_days,
        "dpo_days": dpo_days,
        "ccc_days": ccc_days,
        "total_inventory": total_inventory,
        "available_cash": available_cash,
        "annual_cogs": annual_cogs,
        "annual_sales": annual_sales,
        "frozen_rows": json.dumps(frozen_rows, default=str),
        "overdue_rows": json.dumps(overdue_rows, default=str),
        "under_priced": json.dumps([], default=str),
    }


def _compute_cogs(cfg):
    """COGS من GL (الأدق) أو من حركة المخزون."""
    if cfg["cogs_source"] == "Stock Ledger":
        return flt(frappe.db.sql(
            """
            SELECT SUM(stock_value_difference) * -1
            FROM `tabStock Ledger Entry`
            WHERE voucher_type IN ('Delivery Note', 'Sales Invoice')
            AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
            """
        )[0][0])

    # GL Account
    if cfg["cogs_account"]:
        return flt(frappe.db.sql(
            """
            SELECT SUM(gle.debit - gle.credit)
            FROM `tabGL Entry` gle
            WHERE gle.account = %s
            AND gle.posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
            AND gle.is_cancelled = 0
            """,
            (cfg["cogs_account"],),
        )[0][0])

    # كل حسابات نوع COGS
    return flt(frappe.db.sql(
        """
        SELECT SUM(gle.debit - gle.credit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE acc.account_type = 'Cost of Goods Sold'
        AND gle.posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
        AND gle.is_cancelled = 0
        """
    )[0][0])


def _compute_available_cash(cfg):
    """النقد المتاح من حسابات Cash/Bank، مستبعداً ما حدّده العميل."""
    excluded = cfg["excluded_accounts"]

    if excluded:
        ph = ", ".join(["%s"] * len(excluded))
        return flt(frappe.db.sql(
            """
            SELECT SUM(gle.debit - gle.credit)
            FROM `tabGL Entry` gle
            INNER JOIN `tabAccount` acc ON acc.name = gle.account
            WHERE acc.account_type IN ('Cash', 'Bank')
            AND gle.is_cancelled = 0
            AND acc.name NOT IN ({ph})
            """.format(ph=ph),
            tuple(excluded),
        )[0][0])

    return flt(frappe.db.sql(
        """
        SELECT SUM(gle.debit - gle.credit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE acc.account_type IN ('Cash', 'Bank')
        AND gle.is_cancelled = 0
        """
    )[0][0])


def _compute_monthly_expense(cfg):
    """المصروف الشهري: تلقائي من GL أو يدوي."""
    if not cfg["auto_monthly_expense"]:
        return cfg["manual_monthly_expense"] or 1

    annual_exp = flt(frappe.db.sql(
        """
        SELECT SUM(gle.debit - gle.credit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE acc.root_type = 'Expense'
        AND acc.account_type != 'Cost of Goods Sold'
        AND gle.posting_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
        AND gle.is_cancelled = 0
        """
    )[0][0])

    return (annual_exp / 12) if annual_exp > 0 else 1


def save_snapshot():
    """يحسب ويحفظ snapshot اليوم (يستبدل الموجود إن وُجد)."""
    data = compute_snapshot()
    today = data["snapshot_date"]

    existing = frappe.db.get_value("Cash Pulse Snapshot", {"snapshot_date": today}, "name")
    if existing:
        frappe.delete_doc("Cash Pulse Snapshot", existing, force=1)

    doc = frappe.get_doc(dict(doctype="Cash Pulse Snapshot", **data))
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name
