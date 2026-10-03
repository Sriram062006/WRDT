import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync, useDebounced } from "../lib/useAsync.js";
import { fmtDate, num } from "../lib/format.js";
import { useAuth } from "../lib/auth.jsx";
import { TableCard } from "../components/Card.jsx";
import {
  Badge, Btn, ConfirmModal, EmptyState, ErrorState, Field, IconBtn, InlineError,
  Loading, Modal, PageHead, Pagination, SearchInput, fieldStyle,
} from "../components/ui.jsx";

const PAGE_SIZE = 20;

export default function Groups({ t, ctx, go }) {
  const { isOwner } = useAuth();
  const regionId = ctx?.regionId;
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [modal, setModal] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);

  const list = useAsync(
    () => api.listGroups({ page, page_size: PAGE_SIZE, q: dq || undefined, region_id: regionId }),
    [page, dq, regionId]
  );
  // The create form needs somewhere to put the group; only Owners see it.
  const regions = useAsync(() => (isOwner ? api.listRegions({ page_size: 200 }) : Promise.resolve({ items: [] })), [isOwner]);

  const openAdd = () => {
    setFormError(null);
    setModal({ mode: "add", name: "", regionId: regionId || regions.data?.items?.[0]?.id || "" });
  };

  const save = async (e) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      if (modal.mode === "add") await api.createGroup(modal.regionId, { name: modal.name });
      else await api.updateGroup(modal.group.id, { name: modal.name });
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
      await api.deleteGroup(deleting.id);
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
        title={ctx?.regionName ? `${ctx.regionName} \u2014 ${t.groups}` : t.groups}
        sub={ctx?.regionName ? undefined : "All groups you have access to."}
        back={ctx?.regionName ? { label: t.regions, onClick: () => go("regions") } : undefined}
        actions={isOwner ? <Btn icon="Plus" onClick={openAdd}>{t.addGroup}</Btn> : null}
      />

      <TableCard
        toolbar={<SearchInput value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder={t.search} />}
        footer={list.data && <Pagination page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}
      >
        {list.loading ? (
          <Loading label={t.loading} />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data.items.length === 0 ? (
          <EmptyState
            icon="Users"
            title={dq ? "No groups match that search." : "No groups yet."}
            message={isOwner ? "Create a group, or import your register from Excel." : "No groups have been assigned to you yet."}
          />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.groupName}</th>
                <th className="num">{t.members}</th>
                <th>{t.formedDate}</th>
                <th>{t.status}</th>
                <th style={{ width: 230 }}>{t.action}</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((g) => (
                <tr key={g.id}>
                  <td style={{ fontWeight: 600 }}>{g.name}</td>
                  <td className="num muted">{num(g.members_count)}</td>
                  <td className="muted">{fmtDate(g.formed_date)}</td>
                  <td><Badge s={g.status} /></td>
                  <td>
                    <div className="row wrap" style={{ gap: 6 }}>
                      <Btn size="sm" variant="secondary" onClick={() => go("members", { ...ctx, groupId: g.id, groupName: g.name })}>
                        {t.members}
                      </Btn>
                      <Btn size="sm" variant="secondary" onClick={() => go("meetings", { ...ctx, groupId: g.id, groupName: g.name })}>
                        {t.viewMeetings}
                      </Btn>
                      {isOwner && (
                        <>
                          <IconBtn n="Edit" title={t.edit} onClick={() => { setModal({ mode: "edit", group: g, name: g.name }); setFormError(null); }} />
                          <IconBtn n="Trash2" title={t.del} color="var(--err)" onClick={() => { setDeleting(g); setFormError(null); }} />
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>

      {modal && (
        <Modal title={modal.mode === "add" ? t.addGroup : `${t.edit} ${t.group}`} onClose={() => setModal(null)}>
          <form onSubmit={save}>
            <InlineError error={formError} />
            {modal.mode === "add" && (
              <Field label={t.region}>
                <select
                  required
                  value={modal.regionId}
                  onChange={(e) => setModal({ ...modal, regionId: e.target.value })}
                  style={fieldStyle}
                >
                  <option value="">Select a region</option>
                  {(regions.data?.items || []).map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </Field>
            )}
            <Field label={t.groupName}>
              <input
                autoFocus
                required
                value={modal.name}
                onChange={(e) => setModal({ ...modal, name: e.target.value })}
                placeholder="e.g. Lakshmi SHG"
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
          title="Delete group?"
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={remove}
          message={
            <>
              Delete <strong>{deleting.name}</strong>?
              {deleting.members_count > 0 && (
                <> It has <strong>{deleting.members_count}</strong> member(s), which will be removed with it.</>
              )}{" "}
              Completed meetings remain in the audit history.
            </>
          }
        />
      )}
    </div>
  );
}
