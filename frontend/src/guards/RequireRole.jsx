import { Navigate } from 'react-router-dom';

export default function RequireRole({ user, allowedRoles, children }) {
  if (!user) {
    return <Navigate to="/" replace />;
  }
  const role = user.role;
  const allowed = allowedRoles.some((r) => r === role || role?.startsWith(r));
  if (!allowed) {
    return <Navigate to="/" replace />;
  }
  return children;
}
