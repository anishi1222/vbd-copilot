import { useCallback, useMemo } from "react";
import { useLocation as useWouterLocation, useSearch } from "wouter";

type NavigateOptions = {
  replace?: boolean;
  state?: unknown;
};

export function useNavigate() {
  const [, navigate] = useWouterLocation();

  return useCallback(
    (to: string, options?: NavigateOptions) => navigate(to, options),
    [navigate],
  );
}

export function useLocation() {
  const [pathname] = useWouterLocation();
  return { pathname };
}

export function useSearchParams(): [URLSearchParams] {
  const search = useSearch();
  return [useMemo(() => new URLSearchParams(search), [search])];
}
