// Copyright (c) 2026, SHAMS SOLUTIONS and contributors
/* eslint-disable */

frappe.query_reports["Purchase Forecast"] = {
    "filters": [
        {
            "fieldname": "only_to_order",
            "label": "الأصناف التي تحتاج طلباً فقط",
            "fieldtype": "Check",
            "default": 0
        },
        {
            "fieldname": "only_stockout",
            "label": "الأصناف النافدة فقط",
            "fieldtype": "Check",
            "default": 0
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) {
            return value;
        }

        if (column.fieldname === "status") {
            if (data.status === "نافد") {
                value = `<span style="color:#fff; background:#C0392B; padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px;">${value}</span>`;
            } else if (data.status === "يُطلب") {
                value = `<span style="color:#fff; background:#1E7145; padding:2px 8px; border-radius:4px; font-weight:600; font-size:11px;">${value}</span>`;
            } else {
                value = `<span style="color:#7f8c8d; font-size:11px;">${value}</span>`;
            }
        }
        if (column.fieldname === "to_order" && data.to_order > 0) {
            value = `<b style="color:#1E7145;">${value}</b>`;
        }
        if (column.fieldname === "expired_stock" && data.expired_stock > 0) {
            value = `<span style="color:#E67E22; font-weight:600;">${value}</span>`;
        }
        return value;
    }
};