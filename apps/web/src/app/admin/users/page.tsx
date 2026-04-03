"use client";

/**
 * Admin User Management page.
 *
 * Allows org admins to:
 * - View all users in their organization
 * - Change user roles (viewer / analyst / admin)
 * - Enable or disable user accounts
 *
 * Accessible only to users with the "admin" role.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import {
  fetchUsers,
  updateUserRole,
  updateUserActive,
  type AdminUser,
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
} from "lucide-react";

/** Role badge styling — matches sidebar badges */
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
  const isAdmin = !!user && hasRole("admin");

  // Redirect non-admins (in useEffect to avoid hook ordering violation)
  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/");
    }
  }, [user, isAdmin, router]);

  const { data: users, isLoading, error } = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchUsers,
    enabled: isAdmin,
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      updateUserRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setActionError(null);
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const activeMutation = useMutation({
    mutationFn: ({ userId, isActive }: { userId: number; isActive: boolean }) =>
      updateUserActive(userId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setActionError(null);
    },
    onError: (err: Error) => setActionError(err.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <AlertTriangle className="h-10 w-10 text-yellow-500" />
        <p className="text-muted-foreground">Failed to load users</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">User Management</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage team members and their access levels
        </p>
      </div>

      {/* Error banner */}
      {actionError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Role legend — helpful on mobile */}
      <div className="flex flex-wrap gap-2">
        {(["admin", "analyst", "viewer"] as const).map((role) => {
          const badge = roleBadge[role];
          const Icon = badge.icon;
          return (
            <span
              key={role}
              className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border", badge.bg)}
            >
              <Icon className="h-3 w-3" />
              {role === "admin" && "Full access"}
              {role === "analyst" && "Strategy + AI"}
              {role === "viewer" && "Read-only"}
            </span>
          );
        })}
      </div>

      {/* User list — card layout for mobile, table-like for desktop */}
      <div className="space-y-3">
        {users?.map((u: AdminUser) => {
          const badge = roleBadge[u.role] || roleBadge.viewer;
          const Icon = badge.icon;
          const isSelf = u.id === user?.id;

          return (
            <div
              key={u.id}
              className={cn(
                "rounded-xl border bg-card p-4 transition-colors",
                !u.is_active && "opacity-60",
              )}
            >
              {/* Top row: name + role badge */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-medium text-sm truncate">{u.name}</p>
                    {isSelf && (
                      <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded">
                        You
                      </span>
                    )}
                    {!u.is_active && (
                      <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">
                        Disabled
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">{u.email}</p>
                </div>
                <span className={cn("flex items-center gap-1 text-xs px-2 py-1 rounded border shrink-0", badge.bg)}>
                  <Icon className="h-3 w-3" />
                  {u.role}
                </span>
              </div>

              {/* Actions row — hidden for self */}
              {!isSelf && (
                <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-800">
                  {/* Role selector */}
                  <select
                    value={u.role}
                    onChange={(e) =>
                      roleMutation.mutate({ userId: u.id, role: e.target.value })
                    }
                    disabled={roleMutation.isPending}
                    className="text-xs bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="analyst">Analyst</option>
                    <option value="admin">Admin</option>
                  </select>

                  {/* Active toggle */}
                  <button
                    onClick={() =>
                      activeMutation.mutate({ userId: u.id, isActive: !u.is_active })
                    }
                    disabled={activeMutation.isPending}
                    className={cn(
                      "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors",
                      u.is_active
                        ? "border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
                        : "border-green-500/30 text-green-400 hover:bg-green-500/10",
                    )}
                  >
                    {u.is_active ? (
                      <>
                        <UserX className="h-3 w-3" /> Disable
                      </>
                    ) : (
                      <>
                        <UserCheck className="h-3 w-3" /> Enable
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {users?.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <p>No users found in your organization.</p>
        </div>
      )}
    </div>
  );
}
