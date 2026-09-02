export type UserPermissions = {
  id?: string;
  email?: string | null;
  is_superuser?: boolean;
  roles?: string[];
  permissions?: string[];
};

export function hasPermission(
  me: UserPermissions | null | undefined,
  ...codes: string[]
): boolean {
  if (!me) return false;
  const perms = new Set(me.permissions ?? []);
  if (codes.every((code) => perms.has(code))) return true;
  return Boolean(me.is_superuser);
}
