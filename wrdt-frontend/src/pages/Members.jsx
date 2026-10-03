import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync, useDebounced } from "../lib/useAsync.js";
import { fmtDate, initials, inr } from "../lib/format.js";
import { useAuth } from "../lib/auth.jsx";
import { TableCard } from "../components/Card.jsx";
import {
  Badge, Btn, ConfirmModal, EmptyState, ErrorState, Field, IconBtn, InlineError,
  Loading, Modal, PageHead, Pagination, SearchInput, fieldStyle,
} from "../components/ui.jsx";

const PAGE_SIZE = 20;

export default function Members({ t, ctx, go }) {
  const { isOwner } = useAuth();
  const groupId = ctx?.groupId;
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [modal, setModal] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);

  const list = useAsync(
    () => api.listMembers({ page, page_size: PAGE_SIZE, q: dq || undefined, group_id: groupId }),
    [page, dq, groupId]
  );
  const groups = useAsync(() => api.listGroups({ page_size: 200 }), []);

  const openAdd = () => {
    setFormError(null);
    setModal({
      mode: "add",
      name: "",
      phone: "",
      seed_prev_saving: "0",
      groupId: groupId || groups.data?.items?.[0]?.id || "",
    });
  };

  const save = async (e) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      if (modal.mode === "add") {
        await api.createMember(modal.groupId, {
          name: modal.name,
          phone: modal.phone || null,
          seed_prev_saving: modal.seed_prev_saving || "0",
        });
      } else {
        await api.updateMember(modal.member.id, {
          name: modal.name,
          phone: modal.phone || null,
          seed_prev_saving: modal.seed_prev_saving || "0",
        });
      }
      setModal(null);
      list.reload();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteMember(deleting.id);
      setDeleting(null);
      list.reload();
    } catch (err) {
      setFormError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHead
        title={ctx?.groupName ? `${ctx.groupName} \u2014 ${t.members}` : t.members}
        back={ctx?.groupName ? { label: t.groups, onClick: () => go("groups", { regionId: ctx.regionId, regionName: ctx.regionName }) } : undefined}
        actions={isOwner ? <Btn icon="Plus" onClick={openAdd}>{t.addMember}</Btn> : null}
      />

      <TableCard
        toolbar={<SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Search name or member ID..." />}
        footer={list.data && <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}
      >
        {list.loading ? (
          <Loading label={t.loading} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data.items.length === 0 ? (
          <EmptyState icon="UserCheck" title={dq ? "No members match that search." : "No members yet."} />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.memberCode}</th>
                <th>{t.memberName}</th>
                {!groupId && <th>{t.group}</th>}
                <th>{t.phone}</th>
                <th className="num">{t.prevSavings}</th>
                <th>{t.joinedDate}</th>
                <th>{t.status}</th>
                {isOwner && <th style={{ width: 96 }}>{t.action}</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: "var(--tx2)" }}>{m.code}</td>
                  <td>
                    <button
                      onClick={() => go("memberProfile", { ...ctx, memberId: m.id, memberName: m.name })}
                      style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", padding: 0, textAlign: "left" }}
                    >
                      <span
                        style={{
                          width: 28, height: 28, borderRadius: "50%", background: "var(--brand-bg)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 11, fontWeight: 700, color: "var(--brand)", flexShrink: 0,
                        }}
                      >
                        {initials(m.name)}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--brand)" }}>{m.name}</span>
                    </button>
                  </td>
                  {!groupId && <td className="muted">{m.group_name}</td>}
                  <td className="muted">{m.phone || "\u2014"}</td>
                  <td className="num muted">{inr(m.seed_prev_saving)}</td>
                  <td className="muted">{fmtDate(m.joined_date)}</td>
                  <td><Badge s={m.status} /></td>
                  {isOwner && (
                    <td>
                      <div className="row">
                        <IconBtn
                          n="Edit"
                          title={t.edit}
                          onClick={() => {
                            setFormError(null);
                            setModal({ mode: "edit", member: m, name: m.name, phone: m.phone || "", seed_prev_saving: String(m.seed_prev_saving ?? "0") });
                          }}
                        />
                        <IconBtn n="Trash2" title={t.del} color="var(--err)" onClick={() => { setDeleting(m); setFormError(null); }} />
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>

      {modal && (
        <Modal title={modal.mode === "add" ? t.addMember : `${t.edit} ${t.memberName}`} onClose={() => setModal(null)}>
          <form onSubmit={save}>
            <InlineError error={formError} />
            {modal.mode === "add" && (
              <Field label={t.group}>
                <select required value={modal.groupId} onChange={(e) => setModal({ ...modal, groupId: e.target.value })} style={fieldStyle}>
                  <option value="">Select a group</option>
                  {(groups.data?.items || []).map((g) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </Field>
            )}
            <Field label={t.memberName}>
              <input autoFocus required value={modal.name} onChange={(e) => setModal({ ...modal, name: e.target.value })} style={fieldStyle} />
            </Field>
            <Field label={t.phone}>
              <input value={modal.phone} onChange={(e) => setModal({ ...modal, phone: e.target.value })} style={fieldStyle} inputMode="tel" />
            </Field>
            <Field
              label={t.prevSavings}
              hint="Savings the member already held before WRDT started tracking them. Used only to open their first meeting row."
            >
              <input
                type="number"
                min="0"
                step="1"
                value={modal.seed_prev_saving}
                onChange={(e) => setModal({ ...modal, seed_prev_saving: e.target.value })}
                style={fieldStyle}
              />
            </Field>
            <div className="row" style={{ gap: 10 }}>
              <div className="spacer" />
              <Btn variant="secondary" onClick={() => setModal(null)} disabled={busy}>{t.cancel}</Btn>
              <Btn type="submit" disabled={busy}>{busy ? "Saving..." : t.save}</Btn>
            </div>
          </form>
        </Modal>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete member?"
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={remove}
          message={
            <>
              Remove <strong>{deleting.name}</strong> ({deleting.code})? Their rows in completed
              meetings are kept as permanent history; they are only removed from the currently
              open meeting.
            </>
          }
        />
      )}
    </div>
  );
}
