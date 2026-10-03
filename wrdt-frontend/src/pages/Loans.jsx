import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDate, inr } from "../lib/format.js";
import { TableCard } from "../components/Card.jsx";
import { EmptyState, ErrorState, Loading, PageHead, StatCard } from "../components/ui.jsx";

/**
 * Outstanding loans across every member, as of each member's most
 * recent meeting. This screen was a "Coming Next" placeholder.
 */
export default function Loans({ t, go }) {
  const { data, error, loading, reload } = useAsync(() => api.loanLedger(), []);

  if (loading) return <Loading label={t.loading} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  return (
    <div>
      <PageHead title={t.loanLedger} sub="Balances shown are each member's position at their latest meeting." />

      <div className="stat-grid" style={{ marginBottom: 16 }}>
        <StatCard icon="CreditCard" iconBg="#ef4444" label={t.totalOutstanding} value={inr(data.total_outstanding)} />
        <StatCard icon="UserCheck" iconBg="#f59e0b" label="Members with a balance" value={data.entries.length} />
      </div>

      <TableCard>
        {data.entries.length === 0 ? (
          <EmptyState icon="CheckCircle" title={t.noLoans} message="Nothing is currently owed across your groups." />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.memberName}</th>
                <th>{t.group}</th>
                <th>{t.region}</th>
                <th className="num">{t.remainingLoan}</th>
                <th>{t.asOf}</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e) => (
                <tr key={e.member_id}>
                  <td>
                    <button
                      onClick={() => go("memberProfile", { memberId: e.member_id, memberName: e.member_name, groupId: e.group_id, groupName: e.group_name })}
                      style={{ background: "none", border: "none", padding: 0, color: "var(--brand)", fontWeight: 500, fontSize: 13, textAlign: "left" }}
                    >
                      {e.member_name}
                    </button>
                  </td>
                  <td className="muted">{e.group_name}</td>
                  <td className="muted">{e.region_name}</td>
                  <td className="num" style={{ fontWeight: 700, color: "var(--violet)" }}>
                    {inr(e.loan_remaining)}
                    {e.loan_remaining_manual && (
                      <span title="Manually adjusted" className="tiny" style={{ color: "var(--warn)", marginLeft: 4 }}>&#9998;</span>
                    )}
                  </td>
                  <td className="muted tiny">
                    #{e.as_of_meeting_no} &middot; {fmtDate(e.as_of_meeting_date)}
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
