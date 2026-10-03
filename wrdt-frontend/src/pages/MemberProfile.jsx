import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDate, inr } from "../lib/format.js";
import { Card, TableCard } from "../components/Card.jsx";
import { Badge, EmptyState, ErrorState, Loading, PageHead, StatCard } from "../components/ui.jsx";

/**
 * Member profile and full savings/loan ledger, straight from
 * /reports/members/{id}/ledger. The prototype reconstructed this by
 * walking its in-memory mock store.
 */
export default function MemberProfile({ t, ctx, go }) {
  const { data, error, loading, reload } = useAsync(
    () => api.memberLedger(ctx.memberId),
    [ctx.memberId]
  );

  if (loading) return <Loading label={t.loading} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  return (
    <div>
      <PageHead
        title={data.member_name}
        sub={data.group_name}
        back={{ label: t.members, onClick: () => go("members", ctx) }}
      />

      <div className="stat-grid" style={{ marginBottom: 16 }}>
        <StatCard icon="Receipt" iconBg="#16a34a" label="Current Savings" value={inr(data.current_savings_balance)} />
        <StatCard icon="CreditCard" iconBg="#7c3aed" label="Loan Balance" value={inr(data.current_loan_remaining)} />
        <StatCard icon="CalendarDays" iconBg="#06b6d4" label="Meetings Recorded" value={data.rows.length} />
      </div>

      <TableCard>
        {data.rows.length === 0 ? (
          <EmptyState icon="CalendarDays" title="No meeting history yet." message="This member's ledger fills in as meetings are recorded." />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.meeting}</th>
                <th>{t.date}</th>
                <th>{t.present}</th>
                <th className="num">{t.prevSaving}</th>
                <th className="num">{t.thisWeek}</th>
                <th className="num">{t.loanGiven}</th>
                <th className="num">{t.principalPaid}</th>
                <th className="num">{t.interest}</th>
                <th className="num">{t.fine}</th>
                <th className="num">{t.cashPaid}</th>
                <th className="num">{t.remainingLoan}</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.meeting_id}>
                  <td style={{ fontWeight: 600 }}>#{r.meeting_no}</td>
                  <td className="muted">{fmtDate(r.meeting_date)}</td>
                  <td>{r.present ? <Badge s="Active" /> : <span className="tiny muted">Absent</span>}</td>
                  <td className="num muted">{inr(r.prev_saving)}</td>
                  <td className="num">{inr(r.cur_saving)}</td>
                  <td className="num" style={{ color: Number(r.loan_given) ? "var(--err)" : "var(--txm)" }}>
                    {Number(r.loan_given) ? inr(r.loan_given) : "\u2014"}
                  </td>
                  <td className="num">{Number(r.principal_paid) ? inr(r.principal_paid) : "\u2014"}</td>
                  <td className="num" style={{ color: "var(--violet)" }}>
                    {Number(r.interest_paid) ? inr(r.interest_paid) : "\u2014"}
                  </td>
                  <td className="num" style={{ color: "var(--info)" }}>
                    {Number(r.fine) ? inr(r.fine) : "\u2014"}
                  </td>
                  <td className="num" style={{ fontWeight: 600 }}>{inr(r.cash_paid)}</td>
                  <td className="num" style={{ fontWeight: 600, color: Number(r.loan_remaining) ? "var(--violet)" : "var(--txm)" }}>
                    {Number(r.loan_remaining) ? inr(r.loan_remaining) : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>
    </div>
  );
}
