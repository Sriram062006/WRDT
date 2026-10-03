import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { inr, num, greeting } from "../lib/format.js";
import { useAuth } from "../lib/auth.jsx";
import { Card } from "../components/Card.jsx";
import { EmptyState, ErrorState, Loading, PageHead, StatCard } from "../components/ui.jsx";

/**
 * Dashboard.
 *
 * Every figure here previously came from a hardcoded array -- the
 * "Today's Collection" of Rs.145,600, the 153 groups, the "12% from
 * yesterday" delta and the seven-point chart were all invented and
 * never changed. They now come from /reports/dashboard and
 * /reports/collections, and the fabricated day-over-day delta is gone
 * entirely because the API has no honest basis for it.
 */
export default function Dashboard({ t, go }) {
  const { user, isOwner } = useAuth();
  const stats = useAsync(() => api.dashboard(), []);
  const series = useAsync(() => api.collections(60), []);

  if (stats.loading) return <Loading label={t.loading} />;
  if (stats.error) return <ErrorState error={stats.error} onRetry={stats.reload} />;

  const s = stats.data;
  const cards = [
    { icon: "TrendingUp", iconBg: "#16a34a", label: t.todayCol, value: inr(s.todays_collection) },
    ...(isOwner
      ? [{ icon: "MapPin", iconBg: "#6366f1", label: t.totRegions, value: num(s.total_regions), onClick: () => go("regions") }]
      : []),
    { icon: "Users", iconBg: "#8b5cf6", label: t.totGroups, value: num(s.total_groups), onClick: () => go("groups") },
    { icon: "UserCheck", iconBg: "#f59e0b", label: t.totMembers, value: num(s.total_members), onClick: () => go("members") },
    { icon: "CalendarDays", iconBg: "#06b6d4", label: t.openMeetings, value: num(s.active_meetings), onClick: () => go("groups") },
    { icon: "CheckCircle", iconBg: "#0ea5e9", label: t.completedThisMonth, value: num(s.meetings_completed_this_month) },
    { icon: "CreditCard", iconBg: "#ef4444", label: t.outLoans, value: inr(s.total_loans_outstanding), onClick: () => go("loans") },
    { icon: "Receipt", iconBg: "#16a34a", label: t.totalSavingsHeld, value: inr(s.total_savings) },
  ];

  const points = (series.data || []).map((p) => ({
    d: new Date(p.date + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
    v: p.amount,
  }));

  return (
    <div>
      <PageHead
        title={t.dashboard}
        sub={`${greeting(t)}${user?.full_name ? ", " + user.full_name : ""}`}
      />
      <div className="stat-grid" style={{ marginBottom: 16 }}>
        {cards.map((c) => (
          <StatCard key={c.label} {...c} />
        ))}
      </div>

      <Card title={t.collChart}>
        {series.loading ? (
          <Loading />
        ) : points.length === 0 ? (
          <EmptyState icon="TrendingUp" title={t.noChartData} message="Collections appear here once meetings are recorded." />
        ) : (
          <div style={{ padding: "4px 4px 0" }}>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--bdr)" vertical={false} />
                <XAxis dataKey="d" tick={{ fontSize: 11, fill: "var(--txm)" }} axisLine={false} tickLine={false} minTickGap={18} />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--txm)" }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                  tickFormatter={(v) => (v >= 1000 ? `\u20b9${(v / 1000).toFixed(0)}k` : `\u20b9${v}`)}
                />
                <Tooltip
                  formatter={(v) => [inr(v), "Collected"]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--bdr)" }}
                />
                <Line type="monotone" dataKey="v" stroke="var(--brand)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
