import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDate, inr } from "../lib/format.js";
import { Card, TableCard } from "../components/Card.jsx";
import { EmptyState, ErrorState, Loading, PageHead, fieldStyle } from "../components/ui.jsx";

/**
 * Organization-wide expenses over a date range. Previously a
 * placeholder: expenses only ever existed inside one meeting's register,
 * with no way to see what was actually spent across the programme.
 */
export default function Expenses({ t }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const { data, error, loading, reload } = useAsync(
    () => api.expenseReport({ date_from: from || undefined, date_to: to || undefined }),
    [from, to]
  );

  return (
    <div>
      <PageHead
        title={t.expenses}
        actions={
          <div className="toolbar">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} style={{ ...fieldStyle, width: 160 }} aria-label="From date" />
            <span className="muted tiny">to</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} style={{ ...fieldStyle, width: 160 }} aria-label="To date" />
          </div>
        }
      />

      {loading ? (
        <Loading label={t.loading} />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : (
        <>
          <div className="split-2" style={{ marginBottom: 16 }}>
            <Card title={t.expenseSummary}>
              {data.by_type.length === 0 ? (
                <div className="tiny muted">No expenses in this period.</div>
              ) : (
                data.by_type.map((line) => {
                  const pct = Number(data.total) ? (Number(line.total) / Number(data.total)) * 100 : 0;
                  return (
                    <div key={line.expense_type} style={{ marginBottom: 12 }}>
                      <div className="row" style={{ marginBottom: 4 }}>
                        <span style={{ fontSize: 13 }}>{line.expense_type}</span>
                        <div className="spacer" />
                        <span className="tiny muted">{line.count}&times;</span>
                        <span style={{ fontSize: 13, fontWeight: 600, marginLeft: 10 }}>{inr(line.total)}</span>
                      </div>
                      <div style={{ height: 6, background: "var(--muted)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ width: `${pct}%`, height: "100%", background: "var(--brand)" }} />
                      </div>
                    </div>
                  );
                })
              )}
            </Card>
            <Card>
              <div className="tiny muted">{t.total}</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: "var(--err)" }}>{inr(data.total)}</div>
              <div className="tiny muted" style={{ marginTop: 6 }}>
                {data.rows.length} expense line(s)
                {from || to ? " in the selected period" : " recorded"}
              </div>
            </Card>
          </div>

          <TableCard>
            {data.rows.length === 0 ? (
              <EmptyState icon="Receipt" title="No expenses recorded." message="Expenses are entered on each meeting's register." />
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th>{t.date}</th>
                    <th>{t.group}</th>
                    <th>{t.meeting}</th>
                    <th>{t.expenseType}</th>
                    <th className="num">{t.amount}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.expense_id}>
                      <td className="muted">{fmtDate(r.meeting_date)}</td>
                      <td>{r.group_name}</td>
                      <td className="muted">#{r.meeting_no}</td>
                      <td>{r.expense_type}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{inr(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </TableCard>
        </>
      )}
    </div>
  );
}
