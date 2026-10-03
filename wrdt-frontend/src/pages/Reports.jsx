import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { inr } from "../lib/format.js";
import { useAuth } from "../lib/auth.jsx";
import { Card } from "../components/Card.jsx";
import { ErrorState, Loading, PageHead, fieldStyle } from "../components/ui.jsx";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function Figures({ rows }) {
  return (
    <div className="stat-grid">
      {rows.map(([label, value, color]) => (
        <div key={label} className="card" style={{ padding: 14 }}>
          <div className="tiny muted">{label}</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: color || "var(--tx1)", marginTop: 4 }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

/** Monthly and per-group reports. Previously a placeholder screen. */
export default function Reports({ t }) {
  const { isOwner } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [groupId, setGroupId] = useState("");

  const groups = useAsync(() => api.listGroups({ page_size: 200 }), []);
  const monthly = useAsync(
    () => (isOwner ? api.monthlyReport(year, month) : Promise.resolve(null)),
    [isOwner, year, month]
  );
  const groupReport = useAsync(
    () => (groupId ? api.groupReport(groupId) : Promise.resolve(null)),
    [groupId]
  );

  const years = Array.from({ length: 6 }, (_, i) => now.getFullYear() - i);

  return (
    <div>
      <PageHead title={t.reports} />

      {isOwner && (
        <Card
          title={t.monthlyReport}
          actions={
            <div className="toolbar">
              <select value={month} onChange={(e) => setMonth(Number(e.target.value))} style={{ ...fieldStyle, width: 150 }}>
                {MONTHS.map((m, i) => (
                  <option key={m} value={i + 1}>{m}</option>
                ))}
              </select>
              <select value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ ...fieldStyle, width: 110 }}>
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          }
        >
          {monthly.loading ? (
            <Loading />
          ) : monthly.error ? (
            <ErrorState error={monthly.error} onRetry={monthly.reload} />
          ) : (
            <Figures
              rows={[
                ["Meetings completed", monthly.data.meetings_completed],
                ["Savings collected", inr(monthly.data.total_savings_collected), "var(--ok)"],
                ["Loans disbursed", inr(monthly.data.total_loans_disbursed), "var(--err)"],
                ["Principal repaid", inr(monthly.data.total_loan_repaid)],
                ["Interest collected", inr(monthly.data.total_interest_collected), "var(--violet)"],
                ["Fines collected", inr(monthly.data.total_fines_collected), "var(--info)"],
                ["Expenses", inr(monthly.data.total_expenses), "var(--warn)"],
                ["Net cash movement", inr(monthly.data.cash_in_hand_net), "var(--brand)"],
              ]}
            />
          )}
        </Card>
      )}

      <div style={{ height: 16 }} />

      <Card
        title={t.groupReport}
        actions={
          <select value={groupId} onChange={(e) => setGroupId(e.target.value)} style={{ ...fieldStyle, width: 220 }}>
            <option value="">Select a group</option>
            {(groups.data?.items || []).map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        }
      >
        {!groupId ? (
          <div className="tiny muted">Choose a group to see its lifetime totals.</div>
        ) : groupReport.loading ? (
          <Loading />
        ) : groupReport.error ? (
          <ErrorState error={groupReport.error} onRetry={groupReport.reload} />
        ) : (
          <Figures
            rows={[
              ["Meetings", groupReport.data.meetings_count],
              ["Savings collected", inr(groupReport.data.total_savings_collected), "var(--ok)"],
              ["Loans disbursed", inr(groupReport.data.total_loans_disbursed), "var(--err)"],
              ["Principal repaid", inr(groupReport.data.total_loan_repaid)],
              ["Interest collected", inr(groupReport.data.total_interest_collected), "var(--violet)"],
              ["Fines collected", inr(groupReport.data.total_fines_collected), "var(--info)"],
              ["Expenses", inr(groupReport.data.total_expenses), "var(--warn)"],
              ["Outstanding loans", inr(groupReport.data.current_loan_outstanding), "var(--violet)"],
            ]}
          />
        )}
      </Card>
    </div>
  );
}
