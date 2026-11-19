import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../models/api.js";

export function useCareRecords(api, method, userId, enabled, revision = 0, { poll = false, paused = false } = {}) {
  const [state, setState] = useState({ rows: [], loading: enabled, error: "" });
  const [reload, setReload] = useState(0);
  const refresh = useCallback(() => setReload((value) => value + 1), []);
  useEffect(() => {
    if (!enabled) {
      setState({ rows: [], loading: false, error: "" });
      return;
    }
    if (paused) return;
    const controller = new AbortController();
    let fetching = false;
    setState({ rows: [], loading: true, error: "" });
    const read = async () => {
      if (fetching || controller.signal.aborted) return;
      fetching = true;
      try {
        const rows = await api[method](userId, controller.signal);
        if (!controller.signal.aborted) setState({ rows, loading: false, error: "" });
      } catch (error) {
        if (!controller.signal.aborted) setState({ rows: [], loading: false, error: errorMessage(error) });
      } finally { fetching = false; }
    };
    read();
    const unsubscribe = poll ? api.subscribe(read, () => {}) : () => {};
    if (poll) window.addEventListener("focus", read);
    return () => {
      controller.abort(); unsubscribe();
      if (poll) window.removeEventListener("focus", read);
    };
  }, [api, method, userId, enabled, revision, reload, poll, paused]);
  return { ...state, refresh };
}
