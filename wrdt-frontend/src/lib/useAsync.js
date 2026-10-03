import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Minimal data-fetching hook: loading / error / data / reload.
 *
 * Guards against setting state after unmount and ignores responses from
 * superseded requests -- important on the list screens, where typing in
 * the search box fires overlapping requests and a slow earlier one would
 * otherwise overwrite the newer results.
 */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const seq = useRef(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const run = useCallback(async () => {
    const mine = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fn();
      if (alive.current && mine === seq.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (alive.current && mine === seq.current) setState({ data: null, error, loading: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { ...state, reload: run };
}

/** Debounce a fast-changing value (search boxes). */
export function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
