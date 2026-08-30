# Copyright (c) 2026, SHAMS SOLUTIONS and contributors
# تقرير التنبؤ الشرائي — Script Report

import frappe
from shams_cash_pulse.cash_pulse.forecast_calculator import compute_forecast


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    raw = compute_forecast()

    # فلترة العرض (لا تمسّ الحساب)
    only_order = filters.get("only_to_order")
    only_stockout = filters.get("only_stockout")

    data = []
    for r in raw:
        if only_order and r["to_order"] <= 0:
            continue
        if only_stockout and not r["is_stockout"]:
            continue

        status = "نافد" if r["is_stockout"] else ("يُطلب" if r["to_order"] > 0 else "مكتفٍ")
        data.append({
            "item_code": r["item_code"],
            "item_name": r["item_name"],
            "status": status,
            "sold_period": int(r["sold_period"]),
            "daily_rate": float(r["daily_rate"]),
            "expected_demand": int(r["expected_demand"]),
            "bin_qty": int(r["bin_qty"]),
            "valid_stock": int(r["valid_stock"]),
            "expired_stock": int(r["expired_stock"]),
            "to_order": int(r["to_order"]),
            "rate": float(r["rate"]),
            "order_value": float(r["order_value"]),
            "explanation": r["explanation"],
        })

    return columns, data


def get_columns():
    return [
        {"label": "الكمية المطلوبة", "fieldname": "to_order", "fieldtype": "Int", "width": 120},
        {"label": "الحالة", "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": "الصنف", "fieldname": "item_name", "fieldtype": "Data", "width": 280},
        {"label": "رقم الصنف", "fieldname": "item_code", "fieldtype": "Data", "width": 130},
        {"label": "بيع الفترة", "fieldname": "sold_period", "fieldtype": "Int", "width": 90},
        {"label": "معدّل/يوم", "fieldname": "daily_rate", "fieldtype": "Float", "width": 90, "precision": 2},
        {"label": "الطلب المتوقع", "fieldname": "expected_demand", "fieldtype": "Int", "width": 110},
        {"label": "مخزون", "fieldname": "bin_qty", "fieldtype": "Int", "width": 90},
        {"label": "الصالح", "fieldname": "valid_stock", "fieldtype": "Int", "width": 90},
        {"label": "المهدّد", "fieldname": "expired_stock", "fieldtype": "Int", "width": 90},
        {"label": "التكلفة", "fieldname": "rate", "fieldtype": "Currency", "width": 90},
        {"label": "قيمة الطلب", "fieldname": "order_value", "fieldtype": "Currency", "width": 120},
        {"label": "التوضيح", "fieldname": "explanation", "fieldtype": "Data", "width": 400},
    ]
