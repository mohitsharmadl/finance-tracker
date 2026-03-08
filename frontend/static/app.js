// Finance Tracker v2
(function() {
    "use strict";

    var API = "/api";
    var FIXED_CATEGORIES = ["Rent", "Insurance", "Subscriptions", "EMI / Loans"];
    var COLORS = [
        "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#3b82f6",
        "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#06b6d4",
        "#84cc16", "#e11d48", "#a855f7", "#22c55e", "#0ea5e9",
        "#eab308", "#64748b", "#78716c", "#d946ef", "#2dd4bf",
        "#fb923c", "#94a3b8"
    ];

    var currentTab = "dashboard";
    var currentMonth = "2026-01";
    var donutChart = null;
    var monthlyChart = null;
    var stackedChart = null;
    var allCategories = [];

    // ---- Helpers ----

    function fmt(v) {
        if (v == null || isNaN(v)) return "--";
        var abs = Math.abs(v);
        var s = abs.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        return (v < 0 ? "-" : "") + "\u20B9" + s;
    }

    function pct(v) {
        if (v == null || isNaN(v)) return "--";
        return v.toFixed(1) + "%";
    }

    function fmtDate(d) {
        if (!d) return "--";
        var dt = new Date(d);
        return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
    }

    function truncate(s, n) {
        if (!s) return "";
        return s.length > n ? s.substring(0, n) + "..." : s;
    }

    async function api(path, opts) {
        try {
            var r = await fetch(API + path, opts);
            if (!r.ok) {
                var t = await r.text();
                throw new Error(t || r.statusText);
            }
            return await r.json();
        } catch (e) {
            console.error("API error:", path, e);
            return null;
        }
    }

    // ---- Tab Switching ----

    function switchTab(tab) {
        currentTab = tab;
        document.querySelectorAll(".tab-btn").forEach(function(b) {
            b.classList.toggle("active", b.dataset.tab === tab);
        });
        document.querySelectorAll(".tab-content").forEach(function(c) {
            c.classList.toggle("active", c.id === "tab-" + tab);
        });

        if (tab === "dashboard") loadDashboard();
        else if (tab === "transactions") loadTransactions();
        else if (tab === "trends") loadTrends();
        else if (tab === "upload") loadUploadHistory();
        else if (tab === "ishop") loadCoupons();
        else if (tab === "insights") loadInsights();
    }

    document.querySelectorAll(".tab-btn").forEach(function(btn) {
        btn.addEventListener("click", function() { switchTab(this.dataset.tab); });
    });

    // Set iShop date to today
    var ishopDate = document.getElementById("ishop-date");
    if (ishopDate) ishopDate.valueAsDate = new Date();

    // Load categories for filter dropdown
    async function loadCategories() {
        var data = await api("/categories");
        if (data && data.categories) {
            allCategories = data.categories;
            var sel = document.getElementById("txn-category");
            allCategories.forEach(function(c) {
                var opt = document.createElement("option");
                opt.value = c.id;
                opt.textContent = c.name;
                sel.appendChild(opt);
            });
        }
    }

    // ====================================================================
    //  DASHBOARD
    // ====================================================================

    async function loadDashboard() {
        var data = await api("/summary?month=" + currentMonth);
        if (!data) return;

        var spend = data.total_spend || 0;
        var income = data.total_income || 0;
        var burn = spend - income;

        document.getElementById("dash-total-spend").textContent = fmt(spend);
        document.getElementById("dash-total-income").textContent = fmt(income);
        document.getElementById("dash-spend-txns").textContent = (data.spend_count || 0) + " transactions";
        document.getElementById("dash-income-txns").textContent = (data.income_count || 0) + " transactions";

        var burnEl = document.getElementById("dash-net-burn");
        burnEl.textContent = fmt(burn);
        burnEl.className = "card-value " + (burn > 0 ? "red" : "green");

        var burnSub = document.getElementById("dash-burn-sub");
        burnSub.textContent = burn > 0 ? "Spending exceeds income" : burn < 0 ? "Surplus this month" : "Breakeven";

        renderDonut(data.categories || []);
        renderCategoryTable(data.categories || [], spend);
        updatePeriod();
    }

    function renderDonut(categories) {
        var ctx = document.getElementById("chart-donut").getContext("2d");
        var labels = categories.map(function(c) { return c.name; });
        var values = categories.map(function(c) { return c.amount; });
        var colors = categories.map(function(_, i) { return COLORS[i % COLORS.length]; });

        if (donutChart) donutChart.destroy();

        donutChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{ data: values, backgroundColor: colors, borderColor: "#1e293b", borderWidth: 2 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: "65%",
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: "#94a3b8", font: { family: "Inter", size: 11 }, padding: 12, boxWidth: 12, boxHeight: 12 }
                    },
                    tooltip: { callbacks: { label: function(c) { return c.label + ": " + fmt(c.parsed); } } }
                }
            }
        });
    }

    function renderCategoryTable(categories, totalSpend) {
        var tbody = document.getElementById("cat-breakdown-body");
        if (!categories.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><div class="empty-text">No data for this month</div></td></tr>';
            return;
        }

        tbody.innerHTML = categories.map(function(c, idx) {
            var p = totalSpend > 0 ? (c.amount / totalSpend * 100) : 0;
            var ch = c.change_pct;
            var chHtml;
            if (ch == null) chHtml = '<span style="color:var(--text-muted);">--</span>';
            else if (ch > 0) chHtml = '<span style="color:var(--red);">+' + ch.toFixed(1) + '%</span>';
            else if (ch < 0) chHtml = '<span style="color:var(--green);">' + ch.toFixed(1) + '%</span>';
            else chHtml = '<span style="color:var(--text-muted);">0%</span>';

            var catIdAttr = c.category_id != null ? c.category_id : 0;
            return '<tr class="cat-row" data-cat-id="' + catIdAttr + '" data-cat-idx="' + idx + '" onclick="toggleCategoryDrill(this)">' +
                '<td><span class="cat-expand-icon">&#9654;</span> ' + c.name + '</td>' +
                '<td class="amount-debit">' + fmt(c.amount) + '</td><td>' + pct(p) + '</td><td>' + chHtml + '</td></tr>';
        }).join("");
    }

    window.toggleCategoryDrill = async function(row) {
        var catId = row.dataset.catId;
        var existingDrill = row.nextElementSibling;

        // If already expanded, collapse
        if (existingDrill && existingDrill.classList.contains("cat-drill-row")) {
            existingDrill.remove();
            row.classList.remove("cat-row-expanded");
            return;
        }

        // Collapse any other open drill
        document.querySelectorAll(".cat-drill-row").forEach(function(r) { r.remove(); });
        document.querySelectorAll(".cat-row-expanded").forEach(function(r) { r.classList.remove("cat-row-expanded"); });

        row.classList.add("cat-row-expanded");

        // Fetch transactions for this category
        var params = "?month=" + currentMonth + "&category_id=" + catId + "&txn_type=debit&per_page=500";
        var data = await api("/transactions" + params);
        var txns = (data && data.transactions) || [];

        var drillRow = document.createElement("tr");
        drillRow.className = "cat-drill-row";
        var td = document.createElement("td");
        td.colSpan = 4;

        if (!txns.length) {
            td.innerHTML = '<div class="cat-drill-empty">No transactions</div>';
        } else {
            var html = '<div class="cat-drill-content"><table class="cat-drill-table"><thead><tr>' +
                '<th>Date</th><th>Description</th><th>Amount</th><th>Category</th></tr></thead><tbody>';
            txns.forEach(function(t) {
                var catOpts = '<option value="">Uncategorized</option>';
                allCategories.forEach(function(c) {
                    var sel = (c.id === t.category_id) ? " selected" : "";
                    catOpts += '<option value="' + c.id + '"' + sel + '>' + c.name + '</option>';
                });
                html += '<tr>' +
                    '<td>' + fmtDate(t.date) + '</td>' +
                    '<td title="' + (t.description || "").replace(/"/g, '&quot;') + '">' + truncate(t.description, 45) + '</td>' +
                    '<td class="amount-debit">' + fmt(t.amount) + '</td>' +
                    '<td><select class="cat-select" onchange="updateCategoryAndRefresh(' + t.id + ', this.value)">' + catOpts + '</select></td>' +
                    '</tr>';
            });
            html += '</tbody></table></div>';
            td.innerHTML = html;
        }

        drillRow.appendChild(td);
        row.parentNode.insertBefore(drillRow, row.nextSibling);
    };

    window.updateCategoryAndRefresh = async function(txnId, catId) {
        await api("/transactions/" + txnId + "/category", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category_id: catId ? parseInt(catId) : null })
        });
        // Refresh dashboard to reflect the category change
        loadDashboard();
    };

    // ====================================================================
    //  TRANSACTIONS
    // ====================================================================

    window.loadTransactions = async function() {
        var monthInput = document.getElementById("txn-month");
        var source = document.getElementById("txn-source").value;
        var catId = document.getElementById("txn-category").value;

        var month = monthInput ? monthInput.value : currentMonth;
        var params = "?month=" + month;
        if (source) params += "&source=" + encodeURIComponent(source);
        if (catId) params += "&category_id=" + catId;

        var data = await api("/transactions" + params);
        renderTxnTable(data);
        updateUncatBadge(data);
    };

    function renderTxnTable(data) {
        var tbody = document.getElementById("txn-body");
        var txns = (data && data.transactions) || [];

        if (!txns.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="empty-text">No transactions found</div></td></tr>';
            return;
        }

        tbody.innerHTML = txns.map(function(t) {
            var cls = t.txn_type === "credit" ? "amount-credit" : "amount-debit";
            var pfx = t.txn_type === "credit" ? "+" : "-";

            var catOpts = '<option value="">--</option>';
            allCategories.forEach(function(c) {
                var sel = (c.id === t.category_id) ? " selected" : "";
                catOpts += '<option value="' + c.id + '"' + sel + '>' + c.name + '</option>';
            });

            return '<tr>' +
                '<td>' + fmtDate(t.date) + '</td>' +
                '<td title="' + (t.description || "").replace(/"/g, '&quot;') + '">' + truncate(t.description, 50) + '</td>' +
                '<td class="' + cls + '">' + pfx + fmt(t.amount) + '</td>' +
                '<td><select class="cat-select" onchange="updateCategory(' + t.id + ', this.value)">' + catOpts + '</select></td>' +
                '<td>' + (t.source || "--") + '</td>' +
                '</tr>';
        }).join("");
    }

    function updateUncatBadge(data) {
        var badge = document.getElementById("uncat-badge");
        var count = (data && data.uncategorized_count) || 0;
        if (count > 0) {
            badge.style.display = "inline-flex";
            badge.textContent = count;
        } else {
            badge.style.display = "none";
        }
    }

    window.updateCategory = async function(txnId, catId) {
        await api("/transactions/" + txnId + "/category", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category_id: catId ? parseInt(catId) : null })
        });
    };

    // ====================================================================
    //  TRENDS
    // ====================================================================

    async function loadTrends() {
        var data = await api("/trends?months=6");
        if (!data) return;
        renderMonthlyChart(data);
        renderStackedChart(data);
    }

    function renderMonthlyChart(data) {
        var ctx = document.getElementById("chart-monthly-spend").getContext("2d");
        var months = data.months || [];
        var labels = months.map(function(m) { return m.label; });
        var values = months.map(function(m) { return m.total_spend; });

        if (monthlyChart) monthlyChart.destroy();
        monthlyChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{ label: "Total Spend", data: values, backgroundColor: "rgba(99,102,241,0.7)", borderColor: "#6366f1", borderWidth: 1, borderRadius: 4 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { grid: { color: "rgba(51,65,85,0.3)" }, ticks: { color: "#64748b", font: { family: "Inter", size: 11 } } },
                    y: { grid: { color: "rgba(51,65,85,0.3)" }, ticks: { color: "#64748b", font: { family: "Inter", size: 11 }, callback: function(v) { return fmt(v); } } }
                },
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { return "Spend: " + fmt(c.parsed.y); } } } }
            }
        });
    }

    function renderStackedChart(data) {
        var ctx = document.getElementById("chart-stacked-category").getContext("2d");
        var months = data.months || [];
        var topCats = data.top_categories || [];
        var labels = months.map(function(m) { return m.label; });

        var datasets = topCats.map(function(cat, i) {
            return {
                label: cat,
                data: months.map(function(m) {
                    var found = (m.by_category || []).find(function(c) { return c.name === cat; });
                    return found ? found.amount : 0;
                }),
                backgroundColor: COLORS[i % COLORS.length],
                borderRadius: 2
            };
        });

        if (stackedChart) stackedChart.destroy();
        stackedChart = new Chart(ctx, {
            type: "bar",
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, grid: { color: "rgba(51,65,85,0.3)" }, ticks: { color: "#64748b", font: { family: "Inter", size: 11 } } },
                    y: { stacked: true, grid: { color: "rgba(51,65,85,0.3)" }, ticks: { color: "#64748b", font: { family: "Inter", size: 11 }, callback: function(v) { return fmt(v); } } }
                },
                plugins: {
                    legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter", size: 10 }, boxWidth: 10, boxHeight: 10, padding: 10 } },
                    tooltip: { callbacks: { label: function(c) { return c.dataset.label + ": " + fmt(c.parsed.y); } } }
                }
            }
        });
    }

    // ====================================================================
    //  UPLOAD
    // ====================================================================

    window.handleUpload = async function() {
        var source = document.getElementById("upload-source").value;
        var fileInput = document.getElementById("upload-file");
        var file = fileInput.files[0];

        if (!source) { alert("Please select a source."); return; }
        if (!file) { alert("Please select a file."); return; }

        var btn = document.getElementById("upload-btn");
        var progressEl = document.getElementById("upload-progress");
        var fillEl = document.getElementById("progress-fill");
        var statusEl = document.getElementById("upload-status");

        btn.disabled = true;
        progressEl.classList.add("visible");
        fillEl.style.width = "30%";
        statusEl.textContent = "Uploading...";
        statusEl.className = "upload-status";

        var fd = new FormData();
        fd.append("source", source);
        fd.append("file", file);

        try {
            fillEl.style.width = "60%";
            var resp = await fetch(API + "/upload", { method: "POST", body: fd });
            fillEl.style.width = "90%";

            if (!resp.ok) {
                var errText = await resp.text();
                throw new Error(errText || "Upload failed");
            }

            var result = await resp.json();
            fillEl.style.width = "100%";
            statusEl.textContent = "Done! " + result.inserted + " imported, " + result.skipped + " duplicates skipped.";
            statusEl.className = "upload-status success";

            fileInput.value = "";
            document.getElementById("upload-source").value = "";
            loadUploadHistory();
        } catch (e) {
            fillEl.style.width = "100%";
            fillEl.style.background = "var(--red)";
            statusEl.textContent = "Error: " + e.message;
            statusEl.className = "upload-status error";
        } finally {
            btn.disabled = false;
            setTimeout(function() {
                progressEl.classList.remove("visible");
                fillEl.style.width = "0%";
                fillEl.style.background = "";
            }, 4000);
        }
    };

    async function loadUploadHistory() {
        var data = await api("/uploads");
        var uploads = (data && data.uploads) || [];
        var tbody = document.getElementById("upload-history-body");

        if (!uploads.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="empty-text">No uploads yet</div></td></tr>';
            return;
        }

        tbody.innerHTML = uploads.map(function(u) {
            return '<tr>' +
                '<td>' + (u.filename || "--") + '</td>' +
                '<td>' + (u.source || "--") + '</td>' +
                '<td>' + fmtDate(u.uploaded_at) + '</td>' +
                '<td>' + (u.txn_count || 0) + '</td>' +
                '<td><button class="btn btn-danger btn-sm" onclick="deleteUpload(' + u.id + ')">Delete</button></td>' +
                '</tr>';
        }).join("");
    }

    window.deleteUpload = async function(id) {
        if (!confirm("Delete this upload and all its transactions?")) return;
        await api("/uploads/" + id, { method: "DELETE" });
        loadUploadHistory();
    };

    // ====================================================================
    //  iSHOP
    // ====================================================================

    window.addCoupon = async function() {
        var platform = document.getElementById("ishop-platform").value;
        var amount = parseFloat(document.getElementById("ishop-amount").value);
        var date = document.getElementById("ishop-date").value;

        if (!platform) { alert("Select a platform."); return; }
        if (!amount || amount <= 0) { alert("Enter a valid amount."); return; }
        if (!date) { alert("Select a date."); return; }

        await api("/ishop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ platform: platform, amount: amount, date: date })
        });

        document.getElementById("ishop-amount").value = "";
        loadCoupons();
    };

    async function loadCoupons() {
        var data = await api("/ishop");
        if (!data) return;

        var coupons = data.coupons || [];

        // Summary
        var totalFace = data.total_spent || 0;
        var totalCashback = data.total_cashback || 0;
        var netCost = totalFace - totalCashback;

        document.getElementById("ishop-total-face").textContent = fmt(Math.round(totalFace));
        document.getElementById("ishop-total-cashback").textContent = fmt(Math.round(totalCashback));
        document.getElementById("ishop-net-cost").textContent = fmt(Math.round(netCost));

        // Table
        var tbody = document.getElementById("coupon-body");
        if (!coupons.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="empty-text">No coupons added yet</div></td></tr>';
            return;
        }

        tbody.innerHTML = coupons.map(function(c) {
            var cb = c.cashback_amount || (c.amount * 0.18);
            var net = c.amount - cb;
            return '<tr>' +
                '<td>' + (c.platform || "--") + '</td>' +
                '<td class="amount-neutral">' + fmt(c.amount) + '</td>' +
                '<td class="amount-credit">' + fmt(Math.round(cb)) + '</td>' +
                '<td class="amount-debit">' + fmt(Math.round(net)) + '</td>' +
                '<td>' + fmtDate(c.date) + '</td>' +
                '</tr>';
        }).join("");
    }

    // ====================================================================
    //  INSIGHTS
    // ====================================================================

    async function loadInsights() {
        var data = await api("/insights?month=" + currentMonth);
        if (!data) return;

        // Category changes
        var container = document.getElementById("insight-cards");
        var changes = data.category_changes || [];

        if (!changes.length) {
            container.innerHTML = '<div class="empty-state"><div class="empty-text">Need transaction data to show insights</div></div>';
        } else {
            container.innerHTML = changes.map(function(c) {
                var cls = c.change_pct > 0 ? "up" : "down";
                var sign = c.change_pct > 0 ? "+" : "";
                return '<div class="insight-card">' +
                    '<div class="insight-header">' +
                    '<span class="insight-name">' + c.name + '</span>' +
                    '<span class="insight-change ' + cls + '">' + sign + c.change_pct.toFixed(1) + '%</span>' +
                    '</div>' +
                    '<div class="insight-amounts">This month: ' + fmt(c.current) + ' | Last month: ' + fmt(c.previous) + '</div>' +
                    '</div>';
            }).join("");
        }

        // Suggestions
        var sugContainer = document.getElementById("suggestions-list");
        var suggestions = data.suggestions || [];
        if (!suggestions.length) {
            sugContainer.innerHTML = '<div class="empty-state"><div class="empty-text">No suggestions yet</div></div>';
        } else {
            sugContainer.innerHTML = suggestions.map(function(s) {
                return '<div class="suggestion-card"><div class="suggestion-text">' + s.text + '</div></div>';
            }).join("");
        }

        // Fixed vs Variable
        var fv = data.fixed_vs_variable;
        if (fv) {
            var fixed = fv.fixed || 0;
            var variable = fv.variable || 0;
            var total = fixed + variable;
            if (total > 0) {
                var fixedPct = (fixed / total * 100).toFixed(0);
                var varPct = 100 - parseInt(fixedPct);
                document.getElementById("ratio-labels").innerHTML =
                    '<span>Fixed: ' + fmt(fixed) + '</span><span>Variable: ' + fmt(variable) + '</span>';
                document.getElementById("ratio-bar").innerHTML =
                    '<div class="ratio-bar-fixed" style="width:' + fixedPct + '%;">' + fixedPct + '%</div>' +
                    '<div class="ratio-bar-variable" style="width:' + varPct + '%;">' + varPct + '%</div>';
            }
        }
    }

    // ====================================================================
    //  TABLE SORTING
    // ====================================================================

    var sortState = {};

    window.sortTable = function(tableId, colIndex) {
        var table = document.getElementById(tableId);
        if (!table) return;

        var tbody = table.querySelector("tbody");
        var rows = Array.from(tbody.querySelectorAll("tr"));

        if (rows.length <= 1 && rows[0] && rows[0].querySelector(".empty-state")) return;

        var state = sortState[tableId] || { col: -1, asc: true };
        if (state.col === colIndex) state.asc = !state.asc;
        else { state.col = colIndex; state.asc = true; }
        sortState[tableId] = state;

        rows.sort(function(a, b) {
            var aText = a.cells[colIndex] ? a.cells[colIndex].textContent.trim() : "";
            var bText = b.cells[colIndex] ? b.cells[colIndex].textContent.trim() : "";
            var aNum = parseFloat(aText.replace(/[^\d.-]/g, ""));
            var bNum = parseFloat(bText.replace(/[^\d.-]/g, ""));
            var result = (!isNaN(aNum) && !isNaN(bNum)) ? aNum - bNum : aText.localeCompare(bText);
            return state.asc ? result : -result;
        });

        rows.forEach(function(row) { tbody.appendChild(row); });

        table.querySelectorAll("thead th").forEach(function(th, i) {
            var arrow = th.querySelector(".sort-arrow");
            if (arrow) {
                if (i === colIndex) { arrow.classList.add("active"); arrow.innerHTML = state.asc ? "&#9650;" : "&#9660;"; }
                else { arrow.classList.remove("active"); arrow.innerHTML = "&#9650;"; }
            }
        });
    };

    // ====================================================================
    //  PERIOD
    // ====================================================================

    function updatePeriod() {
        var el = document.getElementById("current-period");
        var parts = currentMonth.split("-");
        var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        el.textContent = months[parseInt(parts[1]) - 1] + " " + parts[0];
    }

    // ====================================================================
    //  INIT
    // ====================================================================

    loadCategories();
    updatePeriod();
    loadDashboard();

})();
