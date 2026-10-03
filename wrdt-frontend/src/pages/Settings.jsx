import { useState } from "react";

import { api } from "../lib/api.js";
import { useAsync } from "../lib/useAsync.js";
import { useAuth } from "../lib/auth.jsx";
import { Card, TableCard } from "../components/Card.jsx";
import {
  Badge, Btn, ConfirmModal, EmptyState, ErrorState, Field, IconBtn, InlineError,
  Loading, Modal, PageHead, fieldStyle,
} from "../components/ui.jsx";

/**
 * Settings: my account (password change) and, for Owners, user
 * management with Supervisor group assignment. Previously a
 * "Coming Next" placeholder, which meant there was no way at all to
 * create the Supervisor accounts the permission model is built around.
 */
export default function Settings({ t, toast }) {
  const { user, role, isOwner } = useAuth();
  return (
    <div>
      <PageHead title={t.settings} />
      <MyAccount t={t} user={user} role={role} toast={toast} />
      {isOwner && (
        <>
          <div style={{ height: 16 }} />
          <UsersPanel t={t} toast={toast} />
        </>
      )}
    </div>
  );
}

function MyAccount({ t, user, role, toast }) {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (form.new_password !== form.confirm) {
      setError({ message: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(form.current_password, form.new_password);
      setForm({ current_password: "", new_password: "", confirm: "" });
      toast("Password changed");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={t.myAccount}>
      <div className="row wrap" style={{ gap: 20, alignItems: "flex-start" }}>
        <div style={{ minWidth: 220 }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{user?.full_name}</div>
          <div className="tiny muted">{user?.email}</div>
          <div style={{ marginTop: 8 }}><Badge s={role} /></div>
        </div>
        <form onSubmit={submit} style={{ flex: 1, minWidth: 260, maxWidth: 380 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{t.changePassword}</div>
          <InlineError error={error} />
          <Field label={t.currentPassword}>
            <input type="password" required autoComplete="current-password" value={form.current_password}
              onChange={(e) => setForm({ ...form, current_password: e.target.value })} style={fieldStyle} />
          </Field>
          <Field label={t.newPassword} hint="At least 10 characters.">
            <input type="password" required minLength={10} autoComplete="new-password" value={form.new_password}
              onChange={(e) => setForm({ ...form, new_password: e.target.value })} style={fieldStyle} />
          </Field>
          <Field label={t.confirmPassword}>
            <input type="password" required minLength={10} autoComplete="new-password" value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })} style={fieldStyle} />
          </Field>
          <Btn type="submit" disabled={busy}>{busy ? "Saving..." : t.changePassword}</Btn>
        </form>
      </div>
    </Card>
  );
}

function UsersPanel({ t, toast }) {
  const { user: me } = useAuth();
  const users = useAsync(() => api.listUsers({ page_size: 100 }), []);
  const roles = useAsync(() => api.listRoles(), []);
  const groups = useAsync(() => api.listGroups({ page_size: 200 }), []);

  const [modal, setModal] = useState(null);
  const [assigning, setAssigning] = useState(null);
  const [deactivating, setDeactivating] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const roleName = (id) => roles.data?.find((r) => r.id === id)?.name || "";
  // Resolved at render time, not captured when the dialog opens: if the
  // roles request is still in flight when "Add User" is clicked, a value
  // captured at that moment would stay empty and the create call would
  // be sent with no role.
  const defaultRoleId =
    roles.data?.find((r) => r.name === "supervisor")?.id || roles.data?.[0]?.id || "";

  const createUser = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createUser({
        role_id: modal.role_id || defaultRoleId,
        email: modal.email.trim(),
        password: modal.password,
        full_name: modal.full_name.trim(),
        phone: modal.phone || null,
      });
      setModal(null);
      users.reload();
      toast("User created");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const deactivate = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.deactivateUser(deactivating.id);
      setDeactivating(null);
      users.reload();
      toast("User deactivated");
    } catch (err) {
      setError(err);
      setDeactivating(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TableCard
        toolbar={
          <>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{t.users}</div>
            <div className="spacer" />
            <Btn
              size="sm"
              icon="Plus"
              onClick={() => {
                setError(null);
                setModal({ email: "", full_name: "", phone: "", password: "", role_id: "" });
              }}
              disabled={!roles.data}
            >
              {t.addUser}
            </Btn>
          </>
        }
      >
        {users.loading || roles.loading ? (
          <Loading />
        ) : users.error ? (
          <ErrorState error={users.error} onRetry={users.reload} />
        ) : users.data.items.length === 0 ? (
          <EmptyState icon="Users" title="No users yet." />
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>{t.name}</th>
                <th>{t.email}</th>
                <th>{t.role}</th>
                <th>{t.status}</th>
                <th style={{ width: 150 }}>{t.action}</th>
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500 }}>
                    {u.full_name}
                    {u.id === me?.id && <span className="tiny muted"> (you)</span>}
                  </td>
                  <td className="muted">{u.email}</td>
                  <td><Badge s={roleName(u.role_id)} /></td>
                  <td><Badge s={u.is_active ? "Active" : "Inactive"} /></td>
                  <td>
                    <div className="row wrap" style={{ gap: 6 }}>
                      {roleName(u.role_id) === "supervisor" && (
                        <Btn size="sm" variant="secondary" onClick={() => setAssigning(u)}>
                          {t.assignedGroups}
                        </Btn>
                      )}
                      {u.id !== me?.id && u.is_active && (
                        <IconBtn n="Trash2" title={t.deactivate} color="var(--err)" onClick={() => setDeactivating(u)} />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </TableCard>

      {error && <div style={{ marginTop: 12 }}><InlineError error={error} /></div>}

      {modal && (
        <Modal title={t.addUser} onClose={() => setModal(null)}>
          <form onSubmit={createUser}>
            <InlineError error={error} />
            <Field label={t.name}>
              <input required autoFocus value={modal.full_name} onChange={(e) => setModal({ ...modal, full_name: e.target.value })} style={fieldStyle} />
            </Field>
            <Field label={t.email}>
              <input required type="email" autoComplete="off" value={modal.email} onChange={(e) => setModal({ ...modal, email: e.target.value })} style={fieldStyle} />
            </Field>
            <Field label={t.password} hint="At least 10 characters. Share it with the user securely; they can change it from Settings.">
              <input required type="password" minLength={10} autoComplete="new-password" value={modal.password}
                onChange={(e) => setModal({ ...modal, password: e.target.value })} style={fieldStyle} />
            </Field>
            <Field label={t.role} hint="Supervisors can only see the groups you assign to them.">
              <select required value={modal.role_id || defaultRoleId} onChange={(e) => setModal({ ...modal, role_id: e.target.value })} style={fieldStyle}>
                {(roles.data || []).map((r) => (
                  <option key={r.id} value={r.id}>{r.name === "owner" ? t.owner : t.supervisor}</option>
                ))}
              </select>
            </Field>
            <div className="row" style={{ gap: 10 }}>
              <div className="spacer" />
              <Btn variant="secondary" onClick={() => setModal(null)} disabled={busy}>{t.cancel}</Btn>
              <Btn type="submit" disabled={busy}>{busy ? "Creating..." : t.save}</Btn>
            </div>
          </form>
        </Modal>
      )}

      {assigning && (
        <AssignGroups
          t={t}
          user={assigning}
          groups={groups.data?.items || []}
          onClose={() => setAssigning(null)}
          toast={toast}
        />
      )}

      {deactivating && (
        <ConfirmModal
          title="Deactivate user?"
          confirmLabel={t.deactivate}
          busy={busy}
          onClose={() => setDeactivating(null)}
          onConfirm={deactivate}
          message={
            <>
              <strong>{deactivating.full_name}</strong> will no longer be able to sign in. Their
              recorded actions and meeting history are kept.
            </>
          }
        />
      )}
    </>
  );
}

function AssignGroups({ t, user, groups, onClose, toast }) {
  const assigned = useAsync(() => api.listAssignments(user.id), [user.id]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const toggle = async (groupId, isAssigned) => {
    setBusy(true);
    setError(null);
    try {
      if (isAssigned) await api.unassignGroup(user.id, groupId);
      else await api.assignGroup(user.id, groupId);
      await assigned.reload();
      toast("Assignments updated");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`${t.assignedGroups} \u2014 ${user.full_name}`} onClose={onClose} width={480}>
      <div className="tiny muted" style={{ marginBottom: 12 }}>
        This supervisor can only open registers for the groups ticked here. The restriction is
        enforced by the server, not just hidden in the interface.
      </div>
      <InlineError error={error} />
      {assigned.loading ? (
        <Loading />
      ) : groups.length === 0 ? (
        <div className="tiny muted">No groups exist yet.</div>
      ) : (
        <div style={{ maxHeight: 320, overflowY: "auto" }}>
          {groups.map((g) => {
            const isAssigned = (assigned.data || []).includes(g.id);
            return (
              <label
                key={g.id}
                className="row"
                style={{ padding: "9px 4px", borderBottom: "1px solid var(--bdr)", gap: 10, cursor: "pointer" }}
              >
                <input
                  type="checkbox"
                  checked={isAssigned}
                  disabled={busy}
                  onChange={() => toggle(g.id, isAssigned)}
                  style={{ accentColor: "var(--brand)", width: 16, height: 16 }}
                />
                <span style={{ fontSize: 13 }}>{g.name}</span>
              </label>
            );
          })}
        </div>
      )}
      <div className="row" style={{ marginTop: 16 }}>
        <div className="spacer" />
        <Btn variant="secondary" onClick={onClose}>{t.close}</Btn>
      </div>
    </Modal>
  );
}
