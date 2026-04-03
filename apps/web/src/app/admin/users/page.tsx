"use client";

/**
 * Admin User & Organization Management page.
 *
 * Allows admins to:
 * - View and manage users (roles, enable/disable, move between orgs)
 * - Create new organizations and link them to IPL teams
 * - Move users between organizations
 *
 * Super-admins (no org) see all users and orgs across the platform.
 * Org-bound admins see only their own org's users.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import {
  fetchUsers,
  fetchTeams,
  fetchOrgs,
  createOrg,
  updateUserRole,
  updateUserActive,
  moveUserToOrg,
  linkOrgToTeam,
  type AdminUser,
  type OrgInfo,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  Shield,
  ShieldCheck,
  Eye,
  UserX,
  UserCheck,
  Loader2,
  AlertTriangle,
  Building2,
  Plus,
  ArrowRightLeft,
  Link2,
} from "lucide-react";

/** Role badge styling */
const roleBadge: Record<string, { bg: string; icon: typeof Shield }> = {
  admin: { bg: "bg-red-500/20 text-red-400 border-red-500/30", icon: ShieldCheck },
  analyst: { bg: "bg-blue-500/20 text-blue-400 border-blue-500/30", icon: Shield },
  viewer: { bg: "bg-gray-500/20 text-gray-400 border-gray-500/30", icon: Eye },
};

export default function UserManagementPage() {
  const { user, hasRole } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"users" | "orgs">("users");
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgTeamId, setNewOrgTeamId] = useState("");
  const isAdmin = !!user && hasRole("admin");

  useEffect(() => {
    if (user && !isAdmin) router.push("/");
  }, [user, isAdmin, router]);

  // --- Queries ---

  const { data: users, isLoading: usersLoading, error: usersError } = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchUsers,
    enabled: isAdmin,
  });

  const { data: orgs } = useQuery({
    queryKey: ["admin-orgs"],
    queryFn: fetchOrgs,
    enabled: isAdmin,
  });

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: fetchTeams,
    enabled: isAdmin,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["admin-orgs"] });
    setActionError(null);
  };

  // --- Mutations ---

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) => updateUserRole(userId, role),
    onSuccess: invalidateAll,
    onError: (err: Error) => setActionError(err.message),
  });

  const activeMutation = useMutation({
    mutationFn: ({ userId, isActive }: { userId: number; isActive: boolean }) => updateUserActive(userId, isActive),
    onSuccess: invalidateAll,
    onError: (err: Error) => setActionError(err.message),
  });

  const moveOrgMutation = useMutation({
    mutationFn: ({ userId, orgId }: { userId: number; orgId: number | null }) => moveUserToOrg(userId, orgId),
    onSuccess: invalidateAll,
    onError: (err: Error) => setActionError(err.message),
  });

  const createOrgMutation = useMutation({
    mutationFn: ({ name, teamId }: { name: string; teamId?: number }) => createOrg(name, teamId),
    onSuccess: () => {
      invalidateAll();
      setNewOrgName("");
      setNewOrgTeamId("");
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const linkTeamMutation = useMutation({
    mutationFn: ({ teamId }: { teamId: number }) => linkOrgToTeam(teamId),
    onSuccess: invalidateAll,
    onError: (err: Error) => setActionError(err.message),
  });

  if (usersLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (usersError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <AlertTriangle className="h-10 w-10 text-yellow-500" />
        <p className="text-muted-foreground">Failed to load users</p>
      </div>
    );
  }

  const activeTeams = (teams || []).filter((t) => t.is_active);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage users, organizations, and team assignments
        </p>
      </div>

      {/* Error banner */}
      {actionError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Tab switcher */}
      <div className="flex gap-1 bg-gray-800/50 rounded-lg p-1">
        <button
          onClick={() => setActiveTab("users")}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 text-sm py-2 rounded-md transition-colors",
            activeTab === "users" ? "bg-gray-700 text-foreground font-medium" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Shield className="h-3.5 w-3.5" /> Users ({users?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("orgs")}
          className={cn(
            "flex-1 flex items-center justify-center gap-1.5 text-sm py-2 rounded-md transition-colors",
            activeTab === "orgs" ? "bg-gray-700 text-foreground font-medium" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Building2 className="h-3.5 w-3.5" /> Organizations ({orgs?.length || 0})
        </button>
      </div>

      {/* ========== Users Tab ========== */}
      {activeTab === "users" && (
        <div className="space-y-3">
          {/* Role legend */}
          <div className="flex flex-wrap gap-2">
            {(["admin", "analyst", "viewer"] as const).map((role) => {
              const badge = roleBadge[role];
              const Icon = badge.icon;
              return (
                <span key={role} className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border", badge.bg)}>
                  <Icon className="h-3 w-3" />
                  {role === "admin" && "Full access"}
                  {role === "analyst" && "Strategy + AI"}
                  {role === "viewer" && "Read-only"}
                </span>
              );
            })}
          </div>

          {/* User cards */}
          {users?.map((u: AdminUser) => {
            const badge = roleBadge[u.role] || roleBadge.viewer;
            const Icon = badge.icon;
            const isSelf = u.id === user?.id;

            return (
              <div
                key={u.id}
                className={cn("rounded-xl border bg-card p-4 transition-colors", !u.is_active && "opacity-60")}
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-sm truncate">{u.name}</p>
                      {isSelf && <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded">You</span>}
                      {!u.is_active && <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">Disabled</span>}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">{u.email}</p>
                    {/* Org badge */}
                    <p className="text-xs text-muted-foreground/70 mt-0.5">
                      {u.organization_name ? (
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3 w-3" /> {u.organization_name}
                          {u.team_name && <span className="text-primary">({u.team_name})</span>}
                        </span>
                      ) : (
                        <span className="italic">No organization</span>
                      )}
                    </p>
                  </div>
                  <span className={cn("flex items-center gap-1 text-xs px-2 py-1 rounded border shrink-0", badge.bg)}>
                    <Icon className="h-3 w-3" /> {u.role}
                  </span>
                </div>

                {/* Actions — hidden for self */}
                {!isSelf && (
                  <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-800">
                    {/* Role selector */}
                    <select
                      value={u.role}
                      onChange={(e) => roleMutation.mutate({ userId: u.id, role: e.target.value })}
                      disabled={roleMutation.isPending}
                      className="text-xs bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="viewer">Viewer</option>
                      <option value="analyst">Analyst</option>
                      <option value="admin">Admin</option>
                    </select>

                    {/* Org selector — move user between orgs */}
                    <select
                      value={u.organization_id ?? ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        moveOrgMutation.mutate({
                          userId: u.id,
                          orgId: val ? parseInt(val) : null,
                        });
                      }}
                      disabled={moveOrgMutation.isPending}
                      className="text-xs bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="">No org</option>
                      {(orgs || []).map((o: OrgInfo) => (
                        <option key={o.id} value={o.id}>{o.name}</option>
                      ))}
                    </select>

                    {/* Active toggle */}
                    <button
                      onClick={() => activeMutation.mutate({ userId: u.id, isActive: !u.is_active })}
                      disabled={activeMutation.isPending}
                      className={cn(
                        "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors",
                        u.is_active
                          ? "border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
                          : "border-green-500/30 text-green-400 hover:bg-green-500/10",
                      )}
                    >
                      {u.is_active ? <><UserX className="h-3 w-3" /> Disable</> : <><UserCheck className="h-3 w-3" /> Enable</>}
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {users?.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <p>No users found.</p>
            </div>
          )}
        </div>
      )}

      {/* ========== Organizations Tab ========== */}
      {activeTab === "orgs" && (
        <div className="space-y-4">
          {/* Create org form */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <p className="text-sm font-medium flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" /> Create Organization
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                placeholder="Organization name"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                className="flex-1 text-sm bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <select
                value={newOrgTeamId}
                onChange={(e) => setNewOrgTeamId(e.target.value)}
                className="text-sm bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">No team (link later)</option>
                {activeTeams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <button
                onClick={() => {
                  if (!newOrgName.trim()) return;
                  createOrgMutation.mutate({
                    name: newOrgName.trim(),
                    teamId: newOrgTeamId ? parseInt(newOrgTeamId) : undefined,
                  });
                }}
                disabled={createOrgMutation.isPending || !newOrgName.trim()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {createOrgMutation.isPending ? "Creating..." : "Create"}
              </button>
            </div>
          </div>

          {/* Org list */}
          {(orgs || []).map((org: OrgInfo) => (
            <div key={org.id} className="rounded-xl border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-sm flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {org.name}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{org.user_count} user{org.user_count !== 1 ? "s" : ""}</span>
                    <span>Plan: {org.plan}</span>
                    {org.team_name && <span className="text-primary">Team: {org.team_name}</span>}
                  </div>
                </div>

                {/* Link team selector (for orgs without a team, or to change) */}
                {user?.organization_id === org.id && (
                  <select
                    value={org.team_id ?? ""}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val)) linkTeamMutation.mutate({ teamId: val });
                    }}
                    disabled={linkTeamMutation.isPending}
                    className="text-xs bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Link team...</option>
                    {activeTeams.map((t) => (
                      <option key={t.id} value={t.id}>{t.short_name}</option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          ))}

          {(orgs || []).length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <p>No organizations yet. Create one above.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
