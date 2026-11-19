import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../models/api.js";
import { mergeReminders, reminderKey } from "../models/reminders.js";

export function useNotifications(api) {
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [delivery, setDelivery] = useState("connecting");
  const [blocked, setBlocked] = useState([]);
  const [announcement, setAnnouncement] = useState("");
  const revision = useRef(0);
  const locked = useRef(false);
  const mounted = useRef(false);

  const refresh = useCallback(async () => {
    const version = ++revision.current;
    setLoading(true);
    try {
      const items = await api.listNotifications();
      if (!mounted.current || version !== revision.current) return;
      setReminders(mergeReminders([], items));
      setBlocked([]);
      setError("");
    } catch (error) {
      if (mounted.current && version === revision.current)
        setError(errorMessage(error));
    } finally {
      if (mounted.current && version === revision.current) setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    mounted.current = true;
    refresh();
    const unsubscribe = api.subscribe(refresh, setDelivery);
    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      mounted.current = false;
      ++revision.current;
      unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [api, refresh]);

  async function answer(reminder, status) {
    const key = reminderKey(reminder);
    if (locked.current || reminder.status !== "sent" || blocked.includes(key))
      return;
    locked.current = true;
    ++revision.current;
    setLoading(false);
    setBusy(key);
    setError("");
    try {
      const updated = await api.answerReminder(reminder, status);
      if (!mounted.current) return;
      ++revision.current;
      setLoading(false);
      setReminders((items) => mergeReminders(items, [updated]));
      setAnnouncement(
        status === "acknowledged"
          ? "Appointment reminder acknowledged."
          : `Medication reminder marked ${status}.`,
      );
      await refresh();
    } catch (error) {
      if (!mounted.current) return;
      if ([404, 409].includes(error.status)) {
        setBlocked((items) => [...items, key]);
        await refresh();
      }
      setError(errorMessage(error));
    } finally {
      locked.current = false;
      if (mounted.current) setBusy("");
    }
  }
  return {
    reminders,
    loading,
    busy,
    error,
    delivery,
    blocked,
    announcement,
    refresh,
    answer,
  };
}
