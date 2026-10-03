import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { fmtDateTime } from "../lib/format.js";
import { TableCard } from "../components/Card.jsx";
import { EmptyState, ErrorState, Loading, PageHead, Pagination } from "../components/ui.jsx";

const PAGE_SIZE = 25;

const LABELS = {
  "region.create": "Created a region", "region.update": "Updated a region", "region.delete": "Deleted a region",
  "group.create": "Created a group", "group.update": "Updated a group", "group.delete": "Deleted a group",
  "member.create": "Added a member", "member.update": "Updated a member", "member.delete": "Removed a member",
  "meeting.start": "Started a meeting", "meeting.complete": "Completed a meeting",
  "meeting_entry.draft_update": "Edited a ledger row", "meeting_entry.bulk_update": "Saved the register",
  "ledger_entry.loan_override": "Overrode a remaining loan", "ledger_entry.loan_reset": "Reset a loan to auto",
  "expense.create": "Added an expense", "expense.update": "Updated an expense", "expense.delete": "Removed an expense",
  "user.create": "Created a user", "user.update": "Updated a user", "user.deactivate": "Deactivated a user",
  "user.change_password": "Changed their password", "user.reset_password": "Reset a user's password",
  "user.assign_group": "Assigned a group", "user.unassign_group": "Unassigned a group",
};

/**
 * Real audit trail, replacing the prototype's Notifications screen --
 * which showed a hardcoded unread badge of "3" with nothing behind it.
 */
export default function Activity({ t }) {
  const [page, setPage] = useState(1);
  const list = useAsync(() => api.activity({ page, page_size: PAGE_SIZE }), [page]);

  return (
    <div>
      <PageHead title={t.activity} sub="Every change recorded in this organization, newest first." />
      <TableCard footer={list.data && <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}>
        {list.loading ? (
          <Loading label={t.loading} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data.items.length === 0 ? (
          <EmptyState icon="Activity" title="No activity recorded yet." />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Entity</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((a) => (
                <tr key={a.id}>
                  <td className="muted tiny" style={{ whiteSpace: "nowrap" }}>{fmtDateTime(a.created_at)}</td>
                  <td>{LABELS[a.action] || a.action}</td>
                  <td className="muted tiny">{a.entity_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>
    </div>
  );
}
