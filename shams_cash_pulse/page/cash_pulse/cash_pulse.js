frappe.pages['cash-pulse'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'نبض النقد — Cash Pulse',
        single_column: true
    });

    var $body = $(page.body);
    var cache = {};
    var anonMode = false;

    // زر التحديث
    page.add_inner_button('تحديث', function () {
        rebuild();
    });
    // زر العرض المجهّل
    var anonBtn = page.add_inner_button('عرض مجهّل', function () {
        anonMode = !anonMode;
        anonBtn.text(anonMode ? 'إظهار الأسماء' : 'عرض مجهّل');
        renderActive();
        drawCharts(cache);
    });

    function fmt(n) {
        try { return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n || 0); }
        catch (e) { return String(Math.round(n || 0)); }
    }

    function anonItem(code, i) { return anonMode ? 'صنف ' + String.fromCharCode(65 + (i % 26)) : code; }
    function anonCustomer(name, i) { return anonMode ? 'عميل ' + (i + 1) : name; }

    $body.html(getShell());

    var views = {
        frozen: {
            title: 'أعلى الأصناف تجميداً للنقد',
            head: '<tr style="background:#f8f9fa;"><th style="text-align:right;padding:10px 14px;font-size:12px;color:#495057;">الصنف</th><th style="text-align:center;padding:10px 8px;font-size:12px;color:#495057;">الكمية</th><th style="text-align:left;padding:10px 14px;font-size:12px;color:#495057;">القيمة المجمّدة</th></tr>',
            rows: function (d) {
                var rows = d.frozen_rows || [];
                var max = rows.length ? rows[0].frozen_value : 1;
                return rows.map(function (r, i) {
                    var pct = max > 0 ? (r.frozen_value / max) * 100 : 0;
                    return '<tr style="border-top:1px solid #f1f3f5;">' +
                        '<td style="padding:10px 14px;color:#212529;">' + anonItem(r.item_code, i) + '</td>' +
                        '<td style="padding:10px 8px;text-align:center;color:#868e96;">' + r.actual_qty + '</td>' +
                        '<td style="padding:10px 14px;text-align:left;"><div style="display:flex;align-items:center;gap:8px;">' +
                        '<div style="flex:1;max-width:70px;height:4px;background:#fdecec;border-radius:2px;overflow:hidden;"><div style="width:' + pct + '%;height:100%;background:#e03131;"></div></div>' +
                        '<span style="font-weight:600;color:#e03131;min-width:60px;">' + fmt(r.frozen_value) + '</span></div></td></tr>';
                }).join('');
            }
        },
        overdue: {
            title: 'أعلى العملاء تأخّراً في السداد',
            head: '<tr style="background:#f8f9fa;"><th style="text-align:right;padding:10px 14px;font-size:12px;color:#495057;">العميل</th><th style="text-align:left;padding:10px 14px;font-size:12px;color:#495057;">المبلغ المتأخر</th></tr>',
            rows: function (d) {
                return (d.overdue_rows || []).map(function (r, i) {
                    return '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;color:#212529;">' + anonCustomer(r.customer, i) + '</td>' +
                        '<td style="padding:10px 14px;text-align:left;font-weight:600;color:#e03131;">' + fmt(r.overdue_amount) + '</td></tr>';
                }).join('');
            }
        },
        ccc: {
            title: 'مكوّنات دورة تحويل النقد',
            head: '<tr style="background:#f8f9fa;"><th style="text-align:right;padding:10px 14px;font-size:12px;color:#495057;">المكوّن</th><th style="text-align:center;padding:10px 14px;font-size:12px;color:#495057;">الأيام</th><th style="text-align:left;padding:10px 14px;font-size:12px;color:#495057;">الأثر</th></tr>',
            rows: function (d) {
                return '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;">+ أيام المخزون (DIO)</td><td style="padding:10px 14px;text-align:center;font-weight:600;">' + Math.round(d.dio_days || 0) + '</td><td style="padding:10px 14px;text-align:left;color:#e03131;">يؤخّر النقد</td></tr>' +
                    '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;">+ أيام التحصيل (DSO)</td><td style="padding:10px 14px;text-align:center;font-weight:600;">' + Math.round(d.dso_days || 0) + '</td><td style="padding:10px 14px;text-align:left;color:#e03131;">يؤخّر النقد</td></tr>' +
                    '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;">− أيام السداد (DPO)</td><td style="padding:10px 14px;text-align:center;font-weight:600;">' + Math.round(d.dpo_days || 0) + '</td><td style="padding:10px 14px;text-align:left;color:#2f9e44;">يؤجّل الخروج</td></tr>' +
                    '<tr style="border-top:2px solid #e9ecef;background:#f8f9fa;"><td style="padding:10px 14px;font-weight:700;">= دورة تحويل النقد</td><td style="padding:10px 14px;text-align:center;font-weight:700;color:#7048e8;">' + Math.round(d.ccc_days || 0) + '</td><td style="padding:10px 14px;text-align:left;font-weight:600;">يوم</td></tr>';
            }
        },
        locked: {
            title: 'تفصيل السيولة المحبوسة',
            head: '<tr style="background:#f8f9fa;"><th style="text-align:right;padding:10px 14px;font-size:12px;color:#495057;">المصدر</th><th style="text-align:left;padding:10px 14px;font-size:12px;color:#495057;">القيمة</th></tr>',
            rows: function (d) {
                var locked = (d.frozen_total || 0) + (d.overdue_total || 0);
                return '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;">نقد مجمّد في المخزون</td><td style="padding:10px 14px;text-align:left;font-weight:600;color:#e03131;">' + fmt(d.frozen_total) + ' ر.س</td></tr>' +
                    '<tr style="border-top:1px solid #f1f3f5;"><td style="padding:10px 14px;">ذمم متأخرة عند العملاء</td><td style="padding:10px 14px;text-align:left;font-weight:600;color:#e8590c;">' + fmt(d.overdue_total) + ' ر.س</td></tr>' +
                    '<tr style="border-top:2px solid #e9ecef;background:#f8f9fa;"><td style="padding:10px 14px;font-weight:600;">الإجمالي القابل للتحرير</td><td style="padding:10px 14px;text-align:left;font-weight:700;">' + fmt(locked) + ' ر.س</td></tr>';
            }
        }
    };

    var activeTarget = 'frozen';

    function renderActive() { render(activeTarget); }

    function render(target) {
        if (!views[target]) return;
        activeTarget = target;
        $body.find('.cp_head').html(views[target].head);
        var b = views[target].rows(cache);
        $body.find('.cp_body').html(b || '<tr><td style="text-align:center;color:#adb5bd;padding:14px;">لا بيانات</td></tr>');
        $body.find('.cp_table_title').text(views[target].title);
    }

    function drawCharts(d) {
        if (typeof frappe === 'undefined' || !frappe.Chart) return;
        var donutEl = $body.find('.cp_donut')[0];
        if (donutEl) {
            donutEl.innerHTML = '';
            new frappe.Chart(donutEl, {
                type: 'donut', height: 180,
                data: { labels: ['نقد مجمّد', 'ذمم متأخرة'], datasets: [{ values: [d.frozen_total || 0, d.overdue_total || 0] }] },
                colors: ['#e03131', '#e8590c']
            });
        }
        var barEl = $body.find('.cp_bar')[0];
        if (barEl) {
            barEl.innerHTML = '';
            var rows = (d.frozen_rows || []).slice(0, 6);
            new frappe.Chart(barEl, {
                type: 'bar', height: 200,
                data: { labels: rows.map(function (r, i) { return anonItem(r.item_code, i); }), datasets: [{ values: rows.map(function (r) { return r.frozen_value; }) }] },
                colors: ['#e03131']
            });
        }
    }

    function fillCards(d) {
        $body.find('.cp_frozen').text(fmt(d.frozen_total));
        $body.find('.cp_frozen_sub').text('ر.س · ≈ ' + (d.months_frozen || 0).toFixed(1) + ' شهر مصروفات');
        $body.find('.cp_frozen_bar').css('width', Math.min(d.frozen_pct || 0, 100) + '%');
        $body.find('.cp_frozen_pct').text((d.frozen_pct || 0).toFixed(0) + '% من المخزون راكد');
        $body.find('.cp_overdue').text(fmt(d.overdue_total));
        $body.find('.cp_overdue_sub').text('ر.س · ' + (d.overdue_rows || []).length + ' عميلاً');
        var ccc = d.ccc_days || 0;
        $body.find('.cp_ccc').text(Math.round(ccc) + ' يوم');
        $body.find('.cp_ccc_sub').text('≈ ' + (ccc / 365).toFixed(1) + ' سنة · المعيار ' + (d.healthy_ccc_days || 60) + ' يوم');
        $body.find('.cp_locked').text(fmt((d.frozen_total || 0) + (d.overdue_total || 0)));
        $body.find('.cp_dio').text(Math.round(d.dio_days || 0) + ' يوم');
        $body.find('.cp_dso_mini').text(Math.round(d.dso_days || 0) + ' يوم');
        $body.find('.cp_dpo').text(Math.round(d.dpo_days || 0) + ' يوم');
        $body.find('.cp_date').text(d.snapshot_date || '');
        $body.find('.cp_inv').text('إجمالي المخزون ' + fmt(d.total_inventory));
    }

    function load() {
        frappe.call({
            method: 'shams_cash_pulse.api.get_cash_pulse_data',
            callback: function (r) {
                if (!r || !r.message || r.message.empty) {
                    $body.find('.cp_body').html('<tr><td style="text-align:center;color:#e03131;padding:14px;">لا يوجد snapshot — اضغط تحديث لبناء أول لقطة</td></tr>');
                    return;
                }
                cache = r.message;
                fillCards(cache);
                render('frozen');
                drawCharts(cache);
            }
        });
    }

    function rebuild() {
        frappe.show_alert({ message: 'جارٍ بناء اللقطة...', indicator: 'blue' });
        frappe.call({
            method: 'shams_cash_pulse.api.rebuild_snapshot',
            callback: function () { load(); frappe.show_alert({ message: 'تم التحديث', indicator: 'green' }); }
        });
    }

    // ربط النقر على البطاقات
    $body.on('click', '.cpcard', function () {
        $body.find('.cpcard').css('border', '1px solid #e9ecef');
        $(this).css('border', '2px solid #e03131');
        render($(this).data('target'));
    });

    load();

    function getShell() {
        return '' +
            '<div style="direction:rtl;font-family:inherit;padding:8px 4px;">' +
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">' +
            '<div style="display:flex;align-items:center;gap:10px;"><div style="width:36px;height:36px;border-radius:10px;background:#fdecec;display:flex;align-items:center;justify-content:center;"><i class="fa fa-heartbeat" style="font-size:18px;color:#e03131;"></i></div><div><div style="font-size:16px;font-weight:600;color:#212529;">نبض النقد</div><div style="font-size:12px;color:#adb5bd;" class="cp_date">—</div></div></div>' +
            '<div style="font-size:12px;color:#495057;background:#f8f9fa;padding:6px 12px;border-radius:8px;border:1px solid #e9ecef;"><span class="cp_inv">—</span></div></div>' +
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin-bottom:16px;direction:rtl;">' +
            card('frozen', 'نقد مجمّد', 'cp_frozen', '#e03131', '2px solid #ffc9c9', true) +
            card('overdue', 'ذمم متأخرة', 'cp_overdue', '#212529', '1px solid #e9ecef', false) +
            card('ccc', 'دورة تحويل النقد', 'cp_ccc', '#7048e8', '1px solid #e9ecef', false) +
            card('locked', 'سيولة محبوسة', 'cp_locked', '#212529', '1px solid #e9ecef', false) +
            '</div>' +
            '<div style="display:flex;gap:10px;margin-bottom:20px;background:#f8f9fa;border:1px solid #e9ecef;border-radius:10px;padding:12px 16px;direction:rtl;flex-wrap:wrap;">' +
            miniKpi('أيام المخزون (DIO)', 'cp_dio') + sep() +
            miniKpi('أيام التحصيل (DSO)', 'cp_dso_mini') + sep() +
            miniKpi('أيام السداد (DPO)', 'cp_dpo') +
            '</div>' +
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;direction:rtl;">' +
            '<div style="background:#fff;border:1px solid #e9ecef;border-radius:12px;padding:14px;"><div style="font-size:13px;font-weight:600;margin-bottom:6px;">توزيع السيولة المحبوسة</div><div class="cp_donut"></div></div>' +
            '<div style="background:#fff;border:1px solid #e9ecef;border-radius:12px;padding:14px;"><div style="font-size:13px;font-weight:600;margin-bottom:6px;">أعلى الأصناف تجميداً</div><div class="cp_bar"></div></div>' +
            '</div>' +
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;"><div style="font-size:13px;font-weight:600;color:#212529;"><span class="cp_table_title">أعلى الأصناف تجميداً للنقد</span></div></div>' +
            '<div style="background:#fff;border:1px solid #e9ecef;border-radius:12px;overflow:hidden;"><table style="width:100%;border-collapse:collapse;font-size:13px;"><thead class="cp_head"></thead><tbody class="cp_body"><tr><td style="text-align:center;color:#adb5bd;padding:14px;">جارٍ التحميل...</td></tr></tbody></table></div>' +
            '</div>';
    }

    function card(target, label, valClass, color, border, withBar) {
        var bar = withBar ? '<div style="margin-top:10px;height:5px;background:#fdecec;border-radius:3px;overflow:hidden;"><div class="cp_frozen_bar" style="width:0%;height:100%;background:#e03131;"></div></div><div class="cp_frozen_pct" style="font-size:10px;color:#adb5bd;margin-top:4px;">—</div>' : '';
        var sub = (target === 'frozen') ? '<div class="cp_frozen_sub" style="font-size:11px;color:#adb5bd;margin-top:6px;">—</div>' :
            (target === 'overdue') ? '<div class="cp_overdue_sub" style="font-size:11px;color:#adb5bd;margin-top:6px;">—</div>' :
                (target === 'ccc') ? '<div class="cp_ccc_sub" style="font-size:11px;color:#adb5bd;margin-top:6px;">—</div>' :
                    '<div style="font-size:11px;color:#adb5bd;margin-top:6px;">مجمّد + متأخر</div>';
        return '<div class="cpcard" data-target="' + target + '" style="background:#fff;border:' + border + ';border-radius:12px;padding:16px;cursor:pointer;">' +
            '<div style="font-size:12px;color:#495057;margin-bottom:10px;">' + label + '</div>' +
            '<div class="' + valClass + '" style="font-size:27px;font-weight:700;color:' + color + ';line-height:1;">—</div>' +
            sub + bar + '</div>';
    }

    function miniKpi(label, cls) {
        return '<div style="flex:1;min-width:120px;text-align:center;"><div style="font-size:11px;color:#868e96;margin-bottom:3px;">' + label + '</div><div class="' + cls + '" style="font-size:18px;font-weight:700;color:#212529;">—</div></div>';
    }
    function sep() { return '<div style="width:1px;background:#dee2e6;"></div>'; }
};
