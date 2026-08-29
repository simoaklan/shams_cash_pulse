# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# منطق التنبؤ الشرائي — Python كامل (لا قيود RestrictedPython)
#
# المنهجية (نضجت عبر تحليل ميداني كامل):
#   الطلب المتوقع = معدّل البيع اليومي × (مدة التوريد + أفق التصريف)
#   الكمية المطلوبة = الطلب المتوقع − المخزون الصالح
#   المخزون الصالح = رصيد Bin موزّع على الدفعات (FEFO)، مستبعداً ما ينتهي قبل تصريفه
#   الانطلاق من الأصناف المُباعة (لا الموجودة) لالتقاط النافد

import frappe
from frappe.utils import flt, nowdate, date_diff, getdate


DEFAULT_SALES_VOUCHERS = ["Sales Invoice", "Delivery Note"]


def _get_settings():
    """يقرأ الإعدادات مع قيم افتراضية آمنة. فارغ = الكل."""
    s = frappe.get_single("Purchase Forecast Settings")

    warehouses = [r.warehouse for r in s.warehouses if r.warehouse]
    suppliers = [r.supplier for r in s.suppliers if r.supplier]
    sales_vouchers = [r.voucher_type for r in s.sales_vouchers if r.voucher_type]
    if not sales_vouchers:
        sales_vouchers = DEFAULT_SALES_VOUCHERS
    sales_entry_types = [r.stock_entry_type for r in s.sales_entry_types if r.stock_entry_type]
    excluded_entry_types = [r.stock_entry_type for r in s.excluded_entry_types if r.stock_entry_type]

    return {
        "lead_time_days": s.lead_time_days or 90,
        "coverage_days": s.coverage_days or 180,
        "measure_period_mode": s.measure_period_mode or "First Sale",
        "measure_start_date": s.measure_start_date,
        "measure_days_manual": s.measure_days_manual or 0,
        "warehouses": warehouses,
        "suppliers": suppliers,
        "sales_vouchers": sales_vouchers,
        "sales_entry_types": sales_entry_types,
        "excluded_entry_types": excluded_entry_types,
        "exclude_cancelled": s.exclude_cancelled,
        "stockout_price_source": s.stockout_price_source or "Item Price",
        "buying_price_list": s.buying_price_list,
        "min_sold_threshold": s.min_sold_threshold or 0,
        "include_new_products": s.include_new_products,
    }


def _warehouse_clause(warehouses, alias="sle"):
    """يبني شرط المستودع. فارغ = الكل (بلا شرط)."""
    if not warehouses:
        return "", []
    placeholders = ", ".join(["%s"] * len(warehouses))
    return " AND {0}.warehouse IN ({1})".format(alias, placeholders), list(warehouses)


def _get_target_items(cfg):
    """
    أصناف الموردين المستهدفين. فارغ = كل الأصناف.
    نربط عبر Item Supplier أو default_supplier.
    """
    if not cfg["suppliers"]:
        return None  # None = كل الأصناف

    ph = ", ".join(["%s"] * len(cfg["suppliers"]))
    rows = frappe.db.sql(
        """
        SELECT DISTINCT i.name
        FROM `tabItem` i
        LEFT JOIN `tabItem Supplier` isup ON isup.parent = i.name
        WHERE i.disabled = 0
        AND (i.default_supplier IN ({ph}) OR isup.supplier IN ({ph}))
        """.format(ph=ph),
        tuple(cfg["suppliers"]) + tuple(cfg["suppliers"]),
        as_dict=True,
    )
    return set(r.name for r in rows)


def _measure_days(cfg):
    """عدد أيام قياس معدّل البيع."""
    mode = cfg["measure_period_mode"]
    if mode == "Manual Days" and cfg["measure_days_manual"]:
        return cfg["measure_days_manual"], None
    if mode == "Fixed Date" and cfg["measure_start_date"]:
        start = getdate(cfg["measure_start_date"])
        return date_diff(nowdate(), start), start
    # First Sale (افتراضي): من أول بيع فعلي
    wh_clause, wh_params = _warehouse_clause(cfg["warehouses"])
    ph = ", ".join(["%s"] * len(cfg["sales_vouchers"]))
    row = frappe.db.sql(
        """
        SELECT MIN(posting_date) AS first_sale
        FROM `tabStock Ledger Entry` sle
        WHERE sle.voucher_type IN ({ph})
        AND sle.actual_qty < 0 {wh}
        """.format(ph=ph, wh=wh_clause),
        tuple(cfg["sales_vouchers"]) + tuple(wh_params),
        as_dict=True,
    )
    first = row[0].get("first_sale") if row else None
    if not first:
        return 1, None
    days = date_diff(nowdate(), first)
    return (days if days > 0 else 1), getdate(first)


def compute_forecast():
    """يحسب قائمة التنبؤ الشرائي الكاملة. يرجّع قائمة صفوف جاهزة للتقرير."""
    cfg = _get_settings()
    horizon = cfg["lead_time_days"] + cfg["coverage_days"]
    measure_days, measure_start = _measure_days(cfg)
    if measure_days < 1:
        measure_days = 1

    target_items = _get_target_items(cfg)

    wh_clause, wh_params = _warehouse_clause(cfg["warehouses"])
    docstatus_clause = " AND si.docstatus = 1" if cfg["exclude_cancelled"] else ""
    se_docstatus_clause = " AND se.docstatus = 1" if cfg["exclude_cancelled"] else ""

    # ===== 1) صافي البيع من مستندات البيع =====
    sv_ph = ", ".join(["%s"] * len(cfg["sales_vouchers"]))
    si_net = frappe.db.sql(
        """
        SELECT sle.item_code, SUM(sle.actual_qty) AS net_qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabSales Invoice` si ON si.name = sle.voucher_no
        WHERE sle.voucher_type = 'Sales Invoice'
        {ds} {wh}
        GROUP BY sle.item_code
        """.format(ds=docstatus_clause, wh=wh_clause),
        tuple(wh_params),
        as_dict=True,
    )
    sold_map = {}
    for r in si_net:
        sold_map[r.item_code] = -(flt(r.net_qty))

    # Delivery Note إن كان ضمن المستندات
    if "Delivery Note" in cfg["sales_vouchers"]:
        dn_clause = " AND dn.docstatus = 1" if cfg["exclude_cancelled"] else ""
        dn_net = frappe.db.sql(
            """
            SELECT sle.item_code, SUM(sle.actual_qty) AS net_qty
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabDelivery Note` dn ON dn.name = sle.voucher_no
            WHERE sle.voucher_type = 'Delivery Note'
            {ds} {wh}
            GROUP BY sle.item_code
            """.format(ds=dn_clause, wh=wh_clause),
            tuple(wh_params),
            as_dict=True,
        )
        for r in dn_net:
            sold_map[r.item_code] = sold_map.get(r.item_code, 0) + (-(flt(r.net_qty)))

    # ===== 2) صرف Stock Entry المحتسب كبيع (عملاء...) =====
    if cfg["sales_entry_types"]:
        et_ph = ", ".join(["%s"] * len(cfg["sales_entry_types"]))
        se_sales = frappe.db.sql(
            """
            SELECT sle.item_code, SUM(sle.actual_qty) AS net_qty
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabStock Entry` se ON se.name = sle.voucher_no
            WHERE sle.voucher_type = 'Stock Entry'
            AND se.stock_entry_type IN ({et})
            AND sle.actual_qty < 0
            {ds} {wh}
            GROUP BY sle.item_code
            """.format(et=et_ph, ds=se_docstatus_clause, wh=wh_clause),
            tuple(cfg["sales_entry_types"]) + tuple(wh_params),
            as_dict=True,
        )
        for r in se_sales:
            sold_map[r.item_code] = sold_map.get(r.item_code, 0) + (-(flt(r.net_qty)))

    # ===== 3) الرصيد الحالي (Bin) =====
    bin_rows = frappe.db.sql(
        """
        SELECT b.item_code, SUM(b.actual_qty) AS qty,
               AVG(NULLIF(b.valuation_rate, 0)) AS rate
        FROM `tabBin` b
        WHERE b.actual_qty > 0 {wh}
        GROUP BY b.item_code
        """.format(wh=_warehouse_clause(cfg["warehouses"], "b")[0]),
        tuple(cfg["warehouses"]),
        as_dict=True,
    )
    bin_map = {}
    for b in bin_rows:
        bin_map[b.item_code] = {"qty": flt(b.qty), "rate": flt(b.rate)}

    # ===== 4) أسماء الأصناف =====
    name_map = {}
    for n in frappe.db.sql("SELECT name, item_name FROM `tabItem`", as_dict=True):
        name_map[n.name] = n.item_name

    # ===== 5) بناء التقرير لكل صنف مُباع =====
    report = []
    for item in sold_map:
        # تصفية بالمورّد المستهدف
        if target_items is not None and item not in target_items:
            continue

        sold = sold_map[item]
        if sold < 0:
            sold = 0

        # الحد الأدنى للبيع
        if cfg["min_sold_threshold"] and sold < cfg["min_sold_threshold"]:
            continue

        daily = sold / measure_days
        expected_demand = daily * horizon

        bin_info = bin_map.get(item)
        bin_qty = bin_info["qty"] if bin_info else 0
        rate = bin_info["rate"] if bin_info else 0
        is_stockout = 1 if bin_qty <= 0 else 0

        if rate <= 0:
            rate = _get_stockout_price(item, cfg)

        valid_qty, expired_qty, expiry_note = _compute_valid_stock(
            item, bin_qty, daily, cfg
        )

        to_order = expected_demand - valid_qty
        if to_order < 0:
            to_order = 0

        explanation = _build_explanation(
            sold, measure_days, daily, horizon, expected_demand,
            bin_qty, valid_qty, expired_qty, to_order, is_stockout, expiry_note
        )

        report.append({
            "item_code": item,
            "item_name": name_map.get(item) or item,
            "sold_period": round(sold, 1),
            "measure_days": measure_days,
            "daily_rate": round(daily, 3),
            "horizon_days": horizon,
            "expected_demand": round(expected_demand, 0),
            "bin_qty": round(bin_qty, 0),
            "valid_stock": round(valid_qty, 0),
            "expired_stock": round(expired_qty, 0),
            "to_order": round(to_order, 0),
            "is_stockout": is_stockout,
            "rate": round(rate, 2),
            "order_value": round(to_order * rate, 2),
            "explanation": explanation,
        })

    # ===== 6) المنتجات الجديدة (لم تُبع) اختيارياً =====
    if cfg["include_new_products"] and target_items:
        for item in target_items:
            if item in sold_map:
                continue
            bin_info = bin_map.get(item)
            bin_qty = bin_info["qty"] if bin_info else 0
            report.append({
                "item_code": item,
                "item_name": name_map.get(item) or item,
                "sold_period": 0,
                "measure_days": measure_days,
                "daily_rate": 0,
                "horizon_days": horizon,
                "expected_demand": 0,
                "bin_qty": round(bin_qty, 0),
                "valid_stock": round(bin_qty, 0),
                "expired_stock": 0,
                "to_order": 0,
                "is_stockout": 1 if bin_qty <= 0 else 0,
                "rate": round(_get_stockout_price(item, cfg), 2),
                "order_value": 0,
                "explanation": "منتج جديد بلا سجلّ بيع — قرار الطلب تجاري (خارج التنبؤ التاريخي).",
            })

    # ترتيب: النافد أولاً، ثم بأعلى قيمة طلب
    report.sort(key=lambda x: (0 if x["is_stockout"] else 1, -x["order_value"]))
    return report


def _compute_valid_stock(item, bin_qty, daily, cfg):
    """
    المخزون الصالح بمنطق FEFO: توزيع رصيد Bin على الدفعات بنسبة batch_qty،
    واستبعاد ما ينتهي قبل تصريفه.
    يرجّع (صالح، مهدّد، ملاحظة).
    """
    if bin_qty <= 0:
        return 0, 0, ""

    batches = frappe.db.sql(
        """
        SELECT bt.batch_qty, bt.expiry_date,
               DATEDIFF(bt.expiry_date, CURDATE()) AS dte
        FROM `tabBatch` bt
        WHERE bt.item = %s AND bt.batch_qty > 0
        ORDER BY bt.expiry_date ASC
        """,
        (item,),
        as_dict=True,
    )

    if not batches:
        # بلا دفعات: كل الرصيد صالح (لا معلومة انتهاء)
        return bin_qty, 0, "بلا تتبّع دفعات — كل الرصيد يُعتبر صالحاً"

    total_batch = 0
    for b in batches:
        total_batch = total_batch + flt(b.batch_qty)

    valid_qty = 0
    expired_qty = 0
    cumulative = 0
    for b in batches:
        bq = flt(b.batch_qty)
        share = (bq / total_batch) * bin_qty if total_batch > 0 else 0
        dte = b.dte

        if daily > 0:
            days_until_sold = cumulative / daily
            days_to_finish = (cumulative + share) / daily
        else:
            days_until_sold = 999999
            days_to_finish = 999999

        if dte is None:
            valid_qty = valid_qty + share
        elif days_until_sold >= dte:
            expired_qty = expired_qty + share
        elif days_to_finish > dte:
            if daily > 0:
                sellable = (dte * daily) - cumulative
                if sellable < 0:
                    sellable = 0
                if sellable > share:
                    sellable = share
                valid_qty = valid_qty + sellable
                expired_qty = expired_qty + (share - sellable)
            else:
                expired_qty = expired_qty + share
        else:
            valid_qty = valid_qty + share
        cumulative = cumulative + share

    note = ""
    if expired_qty > 0:
        note = "يوجد {0:.0f} وحدة مهدّدة بالإتلاف (تنتهي قبل تصريفها)".format(expired_qty)
    return valid_qty, expired_qty, note


def _get_stockout_price(item, cfg):
    """سعر الصنف النافد حسب المصدر المُعدّ."""
    src = cfg["stockout_price_source"]

    if src == "Last Purchase Rate":
        r = frappe.db.sql(
            "SELECT last_purchase_rate FROM `tabItem` WHERE name = %s",
            (item,),
        )
        if r and r[0][0]:
            return flt(r[0][0])

    if src == "Valuation Rate":
        r = frappe.db.sql(
            "SELECT valuation_rate FROM `tabItem` WHERE name = %s",
            (item,),
        )
        if r and r[0][0]:
            return flt(r[0][0])

    # Item Price (افتراضي)
    if cfg["buying_price_list"]:
        r = frappe.db.sql(
            """
            SELECT price_list_rate FROM `tabItem Price`
            WHERE item_code = %s AND buying = 1 AND price_list = %s
            ORDER BY valid_from DESC LIMIT 1
            """,
            (item, cfg["buying_price_list"]),
        )
        if r and r[0][0]:
            return flt(r[0][0])

    r = frappe.db.sql(
        """
        SELECT price_list_rate FROM `tabItem Price`
        WHERE item_code = %s AND buying = 1
        ORDER BY valid_from DESC LIMIT 1
        """,
        (item,),
    )
    if r and r[0][0]:
        return flt(r[0][0])

    # أي سعر متاح
    r = frappe.db.sql(
        """
        SELECT price_list_rate FROM `tabItem Price`
        WHERE item_code = %s ORDER BY valid_from DESC LIMIT 1
        """,
        (item,),
    )
    if r and r[0][0]:
        return flt(r[0][0])

    return 0


def _build_explanation(sold, measure_days, daily, horizon, expected_demand,
                       bin_qty, valid_qty, expired_qty, to_order, is_stockout, expiry_note):
    """يبني نص التوضيح المقروء لقرار كل صنف."""
    parts = []
    parts.append("بيع {0:.0f} وحدة في {1} يوم (معدّل {2:.2f}/يوم)".format(sold, measure_days, daily))
    parts.append("الطلب المتوقع لـ{0} يوم = {1:.0f}".format(horizon, expected_demand))

    if is_stockout:
        parts.append("الصنف نافد تماماً (رصيد صفر) — طلب عاجل")
    else:
        parts.append("المخزون الصالح = {0:.0f}".format(valid_qty))

    if expired_qty > 0:
        parts.append("({0:.0f} مهدّدة بالإتلاف مستبعدة من الصالح)".format(expired_qty))

    if to_order > 0:
        parts.append("← يُطلب {0:.0f}".format(to_order))
    else:
        if not is_stockout and daily > 0:
            cover_days = valid_qty / daily
            parts.append("← لا يُطلب: المخزون الصالح يكفي {0:.0f} يوم (يغطي الأفق)".format(cover_days))
        else:
            parts.append("← لا يُطلب")

    return " · ".join(parts)
