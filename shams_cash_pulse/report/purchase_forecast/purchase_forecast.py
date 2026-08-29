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
            "sold_period": r["sold_period"],
            "daily_rate": r["daily_rate"],
            "expected_demand": r["expected_demand"],
            "bin_qty": r["bin_qty"],
            "valid_stock": r["valid_stock"],
            "expired_stock": r["expired_stock"],
            "to_order": r["to_order"],
            "rate": r["rate"],
            "order_value": r["order_value"],
            "explanation": r["explanation"],
        })

    return columns, data


def get_columns():
    return [
        {"label": "رقم الصنف", "fieldname": "item_code", "fieldtype": "Data", "width": 130},
        {"label": "الصنف", "fieldname": "item_name", "fieldtype": "Data", "width": 260},
        {"label": "الحالة", "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": "بيع الفترة", "fieldname": "sold_period", "fieldtype": "Float", "width": 90, "precision": 0},
        {"label": "معدّل/يوم", "fieldname": "daily_rate", "fieldtype": "Float", "width": 90, "precision": 2},
        {"label": "الطلب المتوقع", "fieldname": "expected_demand", "fieldtype": "Float", "width": 110, "precision": 0},
        {"label": "مخزون Bin", "fieldname": "bin_qty", "fieldtype": "Float", "width": 90, "precision": 0},
        {"label": "الصالح", "fieldname": "valid_stock", "fieldtype": "Float", "width": 90, "precision": 0},
        {"label": "المهدّد", "fieldname": "expired_stock", "fieldtype": "Float", "width": 90, "precision": 0},
        {"label": "الكمية المطلوبة", "fieldname": "to_order", "fieldtype": "Float", "width": 120, "precision": 0},
        {"label": "التكلفة", "fieldname": "rate", "fieldtype": "Currency", "width": 90},
        {"label": "قيمة الطلب", "fieldname": "order_value", "fieldtype": "Currency", "width": 110},
        {"label": "التوضيح", "fieldname": "explanation", "fieldtype": "Data", "width": 500},
    ]
