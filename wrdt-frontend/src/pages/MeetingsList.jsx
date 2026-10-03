import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDate, inr } from "../lib/format.js";
import { TableCard } from "../components/Card.jsx";
import {
  Badge, Btn, EmptyState, ErrorState, InlineError, Loading, PageHead, Pagination,
} from "../components/ui.jsx";

const PAGE_SIZE = 20;

export default function MeetingsList({ t, ctx, go }) {
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const list = useAsync(
    () => api.listMeetings(ctx.groupId, { page, page_size: PAGE_SIZE }),
    [ctx.groupId, page]
  );

  const start = async () => {
    setError(null);
    setBusy(true);
    try {
      // Idempotent server-side: if a meeting is already open for this
      // group it is resumed rather than a second one being created.
      const meeting = await api.startMeeting(ctx.groupId);
      go("register", { ...ctx, meetingId: meeting.id, meetingNo: meeting.meeting_no });
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHead
        title={`${ctx.groupName || t.group} \u2014 ${t.meetings}`}
        back={{ label: t.groups, onClick: () => go("groups", { regionId: ctx.regionId, regionName: ctx.regionName }) }}
        actions={<Btn icon="Plus" onClick={start} disabled={busy}>{busy ? "Opening..." : t.startMeeting}</Btn>}
      />

      <InlineError error={error} />

      <TableCard
        footer={list.data && <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}
      >
        {list.loading ? (
          <Loading label={t.loading} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data.items.length === 0 ? (
          <EmptyState
            icon="CalendarDays"
            title="No meetings recorded yet."
            message="Start the first meeting to open this group's register."
            action={<Btn icon="Plus" onClick={start} disabled={busy}>{t.startMeeting}</Btn>}
          />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.meeting}</th>
                <th>{t.date}</th>
                <th className="num">{t.present}</th>
                <th className="num">{t.savingsCollection}</th>
                <th className="num">{t.loansGiven}</th>
                <th className="num">{t.cashInHand}</th>
                <th>{t.status}</th>
                <th style={{ width: 90 }}>{t.action}</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontWeight: 600 }}>#{m.meeting_no}</td>
                  <td className="muted">{fmtDate(m.meeting_date)}</td>
                  <td className="num muted">{m.members_present}/{m.members_total}</td>
                  <td className="num">{inr(m.total_saving)}</td>
                  <td className="num" style={{ color: Number(m.total_loan) ? "var(--err)" : "var(--txm)" }}>
                    {Number(m.total_loan) ? inr(m.total_loan) : "\u2014"}
                  </td>
                  <td className="num" style={{ fontWeight: 600 }}>{inr(m.cash_in_hand)}</td>
                  <td><Badge s={m.status} /></td>
                  <td>
                    <Btn
                      size="sm"
                      variant="secondary"
                      icon="Eye"
                      onClick={() => go("register", { ...ctx, meetingId: m.id, meetingNo: m.meeting_no })}
                    >
                      {m.status === "in_progress" ? t.openRegister : t.viewRegister}
                    </Btn>
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
