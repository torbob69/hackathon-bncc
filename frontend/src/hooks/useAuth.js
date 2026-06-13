import { useState, useEffect, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';
import { authAPI } from '../api/client';

const TOKEN_KEY = 'koperalink_token';

function decodeUser(token) {
  try {
    const decoded = jwtDecode(token);
    return {
      userId: decoded.sub || decoded.user_id,
      role: decoded.role,
      koperasiId: decoded.koperasi_id,
      exp: decoded.exp,
    };
  } catch {
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      const decoded = decodeUser(token);
      if (decoded && decoded.exp * 1000 > Date.now()) {
        // Fetch full user profile
        authAPI.me()
          .then((res) => {
            setUser({ ...res.data, ...decoded });
          })
          .catch(() => {
            localStorage.removeItem(TOKEN_KEY);
            setUser(null);
          })
          .finally(() => setLoading(false));
      } else {
        localStorage.removeItem(TOKEN_KEY);
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (identifier, password) => {
    const res = await authAPI.login(identifier, password);
    const { access_token } = res.data;
    localStorage.setItem(TOKEN_KEY, access_token);
    const decoded = decodeUser(access_token);
    const meRes = await authAPI.me();
    const fullUser = { ...meRes.data, ...decoded };
    setUser(fullUser);
    return fullUser;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return { user, loading, login, logout };
}
