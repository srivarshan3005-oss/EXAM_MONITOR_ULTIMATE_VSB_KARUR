/* Role-based dashboards: super administrator, examination administrator, department staff, invigilator, student. */
(function () {
  "use strict";
  const { $, esc, api } = EM;
  const today = () => new Date().toISOString().slice(0, 10);
  const stat = (n, l, href) => `<${href ? `a href="${href}"` : "div"} class="stat"><span class="n">${esc(n)}</span><span class="l">${esc(l)}</span></${href ? "a" : "div"}>`;
  const settled = async (...ps) => (await Promise.allSettled(ps)).map(r => (r.status === "fulfilled" ? r.value : null));
  const examRows = list => list.map(e => `<tr><td data-label="Date" class="nowrap">${esc(e.exam_date)}</td><td data-label="Time" class="nowrap">${esc(e.start_time)}–${esc(e.end_time)}</td><td data-label="Examination">${esc(e.title)} <span class="muted">${esc(e.subject_code)}</span></td><td data-label="Status">${EM.statusBadge(e.status)}</td></tr>`).join("");
  const examTable = list => list.length ? `<div class="tablewrap"><table class="table stack"><thead><tr><th>Date</th><th>Time</th><th>Examination</th><th>Status</th></tr></thead><tbody>${examRows(list)}</tbody></table></div>` : EM.empty("No upcoming examinations", "Nothing is scheduled from today onwards.");
  const quick = links => `<div class="row">${links.map(l => `<a class="btn ${l[2] ? "primary" : ""}" href="${l[1]}">${esc(l[0])}</a>`).join("")}</div>`;

  async function staffDash(root) {
    const admin = EM.isAdmin(), u = EM.state.user;
    const [dash, upcoming, drafts, docs, pending, audit, sec] = await settled(
      api("/api/dashboard"), EM.apiList("/api/admin/exams", { date_from: today(), limit: 8 }), EM.apiList("/api/admin/exams", { status: "draft", limit: 1 }),
      api("/api/admin/doc-processing", { params: { status: "needs_review", limit: 100 } }),
      admin ? EM.apiList("/api/admin/users", { status: "pending", limit: 1 }) : null, admin ? api("/api/admin/audit", { params: { limit: 6 } }) : null, admin ? api("/api/admin/security/summary") : null);
    const attention = [];
    if (drafts && drafts.total) attention.push(`<a class="item warn" href="#/exams?status=draft"><div class="t">${drafts.total} draft examination(s)</div><div class="m">Not yet visible to students. Review and publish.</div></a>`);
    if (docs && docs.length) attention.push(`<a class="item warn" href="#/documents"><div class="t">${docs.length} document(s) need review</div><div class="m">Extracted timetable rows are waiting for a decision.</div></a>`);
    if (pending && pending.total) attention.push(`<a class="item warn" href="#/accounts"><div class="t">${pending.total} account(s) awaiting approval</div><div class="m">Pending registrations.</div></a>`);
    if (sec && (sec.critical_events || sec.lockouts)) attention.push(`<a class="item bad" href="#/security"><div class="t">Security attention</div><div class="m">${esc(sec.critical_events)} critical event(s), ${esc(sec.lockouts)} lockout(s) in the last ${esc(sec.window_hours)} h.</div></a>`);
    root.innerHTML = `<div class="stack">
      <div><h2 style="margin-bottom:4px">Welcome, ${esc(u.username)}</h2><p class="muted" style="margin:0">${esc(u.role_label)}${u.department ? " · " + esc(u.department) + " department" : ""}${u.role === "staff" ? " — read/write limited to what your role permits" : ""}</p></div>
      ${dash ? `<div class="grid g4">${stat(dash.students, "Students", "#/students")}${stat(dash.exams, "Examinations", "#/exams")}${stat(dash.allotments, "Seat allotments", "#/allocation")}${stat(dash.published_results, "Published results", admin ? "#/results" : "")}</div>` : EM.alert("Summary figures could not be loaded.", "warn")}
      <section class="card" id="phase10-analytics"><div class="card-head"><h3>Examination intelligence</h3><span class="muted">Live stored-result analytics</span></div>
        <form id="phase10-filter" class="grid g4">
          <div class="field"><label for="a-date-from">From date</label><input id="a-date-from" name="date_from" type="date"></div>
          <div class="field"><label for="a-date-to">To date</label><input id="a-date-to" name="date_to" type="date"></div>
          <div class="field"><label for="a-semester">Semester</label><input id="a-semester" name="semester" type="number" min="1" max="12" placeholder="All"></div>
          <div class="field"><label for="a-subject">Subject ID</label><input id="a-subject" name="subject_id" type="number" min="1" placeholder="All"></div>
          <div class="field"><label for="a-department">Department</label><input id="a-department" name="department" type="text" maxlength="100" value="${esc(u.department || "")}" placeholder="All departments"></div>
          <div class="field"><label for="a-pass">Pass threshold (%)</label><input id="a-pass" name="pass_percent" type="number" min="0" max="100" value="40"></div>
          <div class="row"><button class="btn primary" type="submit">Apply filters</button><button class="btn" type="button" id="a-export">Export performance</button></div>
        </form><div id="phase10-metrics" class="muted">Loading analytics…</div>
      </section>
      <div class="grid g2"><section class="card"><div class="card-head"><h3>Needs attention</h3></div>${attention.length ? `<div class="list">${attention.join("")}</div>` : EM.empty("All clear", "Nothing is waiting for you.")}</section>
      <section class="card"><div class="card-head"><h3>Quick actions</h3></div>${quick([["New examination", "#/exams?new=1", true], ["Seat allocation", "#/allocation"], ["Reports & seating plans", "#/reports"], ["Upload timetable PDF", "#/documents"]].concat(admin ? [["Create account", "#/accounts"]] : []))}</section></div>
      <section class="card"><div class="card-head"><h3>Upcoming examinations</h3><a href="#/exams">All examinations</a></div>${upcoming ? examTable(upcoming.rows) : EM.alert("Examinations could not be loaded.", "warn")}</section>
      ${admin ? `<div class="grid g2"><section class="card"><div class="card-head"><h3>Recent administrative activity</h3><a href="#/audit">Audit history</a></div>${audit ? (audit.length ? `<div class="list">${audit.map(a => `<div class="item"><div class="t">${esc(a.action)}</div><div class="m">${EM.fmtDT(a.created_at)} · ${esc(a.actor)} · ${esc(a.target)}</div></div>`).join("")}</div>` : EM.empty("No activity yet")) : ""}</section>
      <section class="card"><div class="card-head"><h3>Security (last ${sec ? esc(sec.window_hours) : "24"} h)</h3><a href="#/security">Security dashboard</a></div>${sec ? `<div class="grid g2">${stat(sec.successful_logins, "sign-ins")}${stat(sec.failed_logins, "failed sign-ins")}${stat(sec.permission_denials, "permission denials")}${stat(sec.active_sessions, "active sessions")}</div>` : ""}</section></div>` : ""}</div>`;
    const panel = $("#phase10-metrics", root), form = $("#phase10-filter", root);
    const drawAnalytics = async params => {
      panel.textContent = "Loading analytics…";
      try {
        const data = await api("/api/analytics/dashboard", { params });
        const p = data.performance, a = data.allocation;
        const bars = (data.by_subject || []).map(x => `<div class="item"><div class="row" style="justify-content:space-between"><b>${esc(x.name)}</b><span>${esc(x.average_percent)}%</span></div><div style="height:8px;background:var(--line);border-radius:8px;overflow:hidden"><div style="height:8px;width:${Math.max(0, Math.min(100, Number(x.average_percent) || 0))}%;background:var(--accent)"></div></div><small class="muted">${esc(x.records)} results · ${esc(x.pass_count)} pass · ${esc(x.fail_count)} fail</small></div>`).join("");
        panel.innerHTML = `<div class="grid g4" style="margin-top:14px">
          ${stat(p.result_records, "Result records")}${stat(p.average_percent == null ? "—" : p.average_percent + "%", "Average score")}${stat(p.pass_rate_percent == null ? "—" : p.pass_rate_percent + "%", "Pass rate")}${stat(a.allocation_rate_percent == null ? "—" : a.allocation_rate_percent + "%", "Seat allocation rate")}</div>
          <div class="grid g2" style="margin-top:14px"><div><h4>Subject performance</h4>${bars || EM.empty("No subject results", "No matching stored result rows.")}</div>
          <div><h4>Examination trend</h4>${data.trend.length ? `<div class="list">${data.trend.map(x => `<div class="item"><b>${esc(x.exam_title)}</b><div class="m">${esc(x.date)} · ${esc(x.records)} results · average ${esc(x.average_percent)}%</div></div>`).join("")}</div>` : EM.empty("No trend data")}</div></div>
          <p class="muted">Pass threshold: ${esc(data.data_quality.pass_threshold_percent)}%. Attendance: unavailable (no attendance records in the current database). No estimates or missing scores are added.</p>`;
      } catch (e) { panel.innerHTML = EM.alert(e.message || "Analytics unavailable.", "warn"); }
    };
    const currentFilters = () => {
      const f = EM.formData(form);
      return { date_from: f.date_from, date_to: f.date_to, semester: f.semester, subject_id: f.subject_id,
               department: f.department, pass_percent: f.pass_percent };
    };
    form.addEventListener("submit", ev => { ev.preventDefault(); drawAnalytics(currentFilters()); });
    $("#a-export", root).addEventListener("click", () => {
      const params = Object.assign({}, currentFilters(), { format: "xlsx" });
      EM.download("/api/analytics/reports/performance?" + EM.qs(params), "performance_analytics.xlsx").catch(EM.fail);
    });
    drawAnalytics(currentFilters());
  }

  async function invigilatorDash(root) {
    const [list, analytics] = await Promise.allSettled([
      EM.apiList("/api/admin/exams", { date_from: today(), limit: 20 }),
      api("/api/analytics/dashboard")
    ]);
    const rows = list.status === "fulfilled" ? list.value.rows : [];
    const a = analytics.status === "fulfilled" ? analytics.value : null;
    root.innerHTML = `<div class="stack"><div><h2 style="margin-bottom:4px">Invigilator desk</h2><p class="muted" style="margin:0">Read-only access to hall rosters and seating charts for examinations you supervise.</p></div>
      ${a ? `<section class="card"><div class="card-head"><h3>Institutional performance snapshot</h3></div><div class="grid g3">${stat(a.performance.result_records, "Result records")}${stat(a.performance.average_percent == null ? "—" : a.performance.average_percent + "%", "Average score")}${stat(a.performance.pass_rate_percent == null ? "—" : a.performance.pass_rate_percent + "%", "Pass rate")}</div><p class="muted">Aggregate read-only data. Attendance is unavailable in the current database.</p></section>` : ""}
      <section class="card"><div class="card-head"><h3>Upcoming examinations</h3></div>${rows.length ? `<div class="tablewrap"><table class="table stack"><thead><tr><th>Date</th><th>Time</th><th>Examination</th><th>Venue</th><th>Seats</th><th>Open</th></tr></thead><tbody>${rows.map(e => `<tr><td data-label="Date" class="nowrap">${esc(e.exam_date)}</td><td data-label="Time" class="nowrap">${esc(e.start_time)}–${esc(e.end_time)}</td><td data-label="Examination">${esc(e.title)} <span class="muted">${esc(e.subject_code)}</span></td><td data-label="Venue">${esc(e.venue)}</td><td data-label="Seats">${esc(e.allotment_count)}</td><td class="actions" data-label="Open"><a class="btn sm primary" href="#/rosters/${e.id}">Roster</a><a class="btn sm" href="#/seating/${e.id}">Seating chart</a></td></tr>`).join("")}</tbody></table></div>` : EM.empty("No upcoming examinations")}</section></div>`;
  }

  async function studentDash(root) {
    const u = EM.state.user, reg = u.register_number;
    const [ann] = await settled(api("/api/announcements", { auth: false }));
    let body = "";
    if (!reg) body = EM.alert("Your account is not linked to a student record yet. Ask the examination office to link it; seats and results will then appear here.", "warn");
    else {
      const [lk, res, analytics] = await settled(api("/api/lookup/" + encodeURIComponent(reg)), api("/api/results/" + encodeURIComponent(reg)), api("/api/analytics/me"));
      const seats = lk ? lk.allotments : [];
      body = `<div class="grid g3">${stat(seats.length, "Published seat allotments", "#/my-exams")}${stat(res ? res.length : "—", "Published results", "#/my-results")}${stat(reg, "Register number")}</div>
        ${analytics ? `<section class="card"><div class="card-head"><h3>My academic progress</h3></div>${analytics.subject_progress.length ? `<div class="list">${analytics.subject_progress.map(x => `<div class="item"><b>${esc(x.subject_code)}</b><div class="m">${esc(x.attempts)} published result(s) · first ${esc(x.first_percent)}% · latest ${esc(x.latest_percent)}% · change ${esc(x.change_percentage_points)} percentage points</div></div>`).join("")}</div>` : EM.empty("No published progress data yet")}</section>` : ""}
        <section class="card"><div class="card-head"><h3>My examinations and seats</h3><a href="#/my-exams">Details</a></div>${lk ? (seats.length ? `<div class="list">${seats.slice(0, 5).map(x => `<div class="item"><div class="t">${esc(x.exam)} <span class="muted">${esc(x.subject_code)}</span></div><div class="m">${esc(x.date)} · ${esc(x.time)} · Hall <b>${esc(x.hall)}</b> · Seat <b>${esc(x.seat)}</b></div></div>`).join("")}</div>` : EM.empty("No published seat allotment yet", "Your seat appears here once the examination is published.")) : EM.alert("Seat information could not be loaded.", "warn")}</section>`;
    }
    root.innerHTML = `<div class="stack"><div><h2 style="margin-bottom:4px">Hello, ${esc(u.student_name || u.username)}</h2><p class="muted" style="margin:0">Student portal — your timetable, seating and published results.</p></div>${body}
      <section class="card"><div class="card-head"><h3>Announcements</h3></div>${ann && ann.length ? `<div class="list">${ann.map(a => `<div class="item"><div class="t">${esc(a.title)}</div><div class="m" style="white-space:pre-wrap">${esc(a.body)}</div></div>`).join("")}</div>` : EM.empty("No current announcements")}</section></div>`;
  }

  EM.page({ name: "dashboard", title: "Dashboard", nav: { group: "Overview", icon: "⌂", label: "Dashboard", order: 1 }, render: root => {
    const r = EM.role();
    return r === "student" ? studentDash(root) : r === "invigilator" ? invigilatorDash(root) : staffDash(root);
  } });

  // ------------------------------------------------------------ student pages
  EM.page({ name: "my-exams", title: "My examinations & seats", roles: ["student"], nav: { group: "Overview", icon: "🗓", label: "My exams & seats", order: 2 }, render: async root => {
    const reg = EM.state.user.register_number;
    if (!reg) { root.innerHTML = EM.alert("Your account is not linked to a student record.", "warn"); return; }
    const [lk, exams] = await Promise.all([api("/api/lookup/" + encodeURIComponent(reg)), api("/api/exams", { auth: false })]);
    const seatBy = {}; lk.allotments.forEach(a => { seatBy[a.subject_code + "|" + a.date] = a; });
    root.innerHTML = `<div class="stack"><section class="card"><div class="card-head"><h2>My seats</h2></div>${lk.allotments.length ? `<div class="list">${lk.allotments.map(x => `<div class="item"><div class="t">${esc(x.exam)} <span class="muted">(${esc(x.subject_code)})</span></div><div class="m">${esc(x.date)} · ${esc(x.time)} · Hall <b>${esc(x.hall)}</b> · Seat <b>${esc(x.seat)}</b>${x.location ? " · " + esc(Object.values(x.location).filter(Boolean).join(" / ")) : ""}</div></div>`).join("")}</div>` : EM.empty("No published seat allotment yet")}</section>
      <section class="card"><div class="card-head"><h2>Published timetable</h2><span class="muted small">All published examinations (your seats are shown above)</span></div>${exams.length ? EM.timetableTable(exams) : EM.empty("No published examinations")}</section></div>`;
  } });
  EM.page({ name: "my-results", title: "My results", roles: ["student"], nav: { group: "Overview", icon: "🎓", label: "My results", order: 3 }, render: async root => {
    const reg = EM.state.user.register_number;
    root.innerHTML = `<section class="card"><div class="card-head"><h2>Published results</h2></div>${reg ? await EM.resultsHtml(reg, true) : EM.alert("Your account is not linked to a student record.", "warn")}</section>`;
  } });
  EM.page({ name: "announcements-view", title: "Announcements", roles: ["student", "invigilator"], nav: { group: "Overview", icon: "📣", label: "Announcements", order: 4 }, render: async root => {
    const a = await api("/api/announcements", { auth: false });
    root.innerHTML = `<section class="card"><div class="card-head"><h2>Announcements</h2></div>${a.length ? `<div class="list">${a.map(x => `<div class="item"><div class="t">${esc(x.title)}</div><div class="m" style="white-space:pre-wrap">${esc(x.body)}</div></div>`).join("")}</div>` : EM.empty("No current announcements")}</section>`;
  } });
})();
