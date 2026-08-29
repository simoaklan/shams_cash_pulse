app_name = "shams_cash_pulse"
app_title = "Cash Pulse"
app_publisher = "SHAMS SOLUTIONS"
app_description = "لوحة نبض النقد لمتابعة السيولة ودورة تحويل النقد في ERPNext"
app_email = "info@shamss.store"
app_license = "MIT"
app_version = "0.2.0"

# المهام المجدولة
# ------------------------------
# يبني snapshot يومي تلقائياً كل ليلة
scheduler_events = {
    "daily": [
        "shams_cash_pulse.tasks.build_daily_snapshot"
    ]
}

# الأصول (تُضاف لاحقاً عند بناء صفحة الداشبورد)
# app_include_js = "/assets/shams_cash_pulse/js/cash_pulse.js"
# app_include_css = "/assets/shams_cash_pulse/css/cash_pulse.css"

# التركيب
# ------------------------------
after_install = "shams_cash_pulse.install.after_install"
