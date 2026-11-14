import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../models/api.js";

export function useConversation(api) {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      text: "Hello. How can I help you today?",
    },
  ]);
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [failedText, setFailedText] = useState("");
  const locked = useRef(false);
  const conversationId = useRef(null);
  const [pendingReady, setPendingReady] = useState(false);
  const [pendingError, setPendingError] = useState("");
  const [careRevision, setCareRevision] = useState(0);
  const mounted = useRef(false);
  const restoreVersion = useRef(0);
  const restorePending = useCallback(async () => {
    const version = ++restoreVersion.current;
    setPendingReady(false);
    setPendingError("");
    try {
      const action = await api.getPendingAction();
      if (!mounted.current || version !== restoreVersion.current) return;
      setProposal(action);
      setPendingReady(true);
    } catch (error) {
      if (mounted.current && version === restoreVersion.current)
        setPendingError(errorMessage(error));
    }
  }, [api]);
  useEffect(() => {
    mounted.current = true;
    restorePending();
    return () => {
      mounted.current = false;
      ++restoreVersion.current;
    };
  }, [restorePending]);
  const append = (role, text, notice = "") =>
    setMessages((items) => [
      ...items,
      { id: crypto.randomUUID(), role, text, notice },
    ]);

  async function send(text, retry = false) {
    const clean = text.trim();
    if (!clean || locked.current || proposal || !pendingReady) return false;
    locked.current = true;
    setBusy("thinking");
    setError("");
    setFailedText("");
    if (!retry) append("user", clean);
    try {
      const reply = await api.converse(clean, conversationId.current);
      append("assistant", reply.text, reply.notice);
      setProposal(reply.proposal);
      conversationId.current = reply.conversation_id ?? conversationId.current;
    } catch (error) {
      setError(errorMessage(error));
      setFailedText(clean);
    } finally {
      locked.current = false;
      setBusy("");
    }
    return true;
  }

  async function proposeAppointment(slot) {
    if (locked.current || proposal || !pendingReady) return false;
    locked.current = true;
    setBusy("proposing");
    setError("");
    setFailedText("");
    try {
      const action = await api.proposeAppointment(slot.slot_id);
      if (!mounted.current) return false;
      append("assistant", action.summary);
      setProposal(action);
      return true;
    } catch (error) {
      if (!mounted.current) return false;
      setError(errorMessage(error));
      // A timeout may have happened after the server saved the action. Recover
      // it before permitting another proposal, which would replace the first.
      await restorePending();
      return false;
    } finally {
      locked.current = false;
      if (mounted.current) setBusy("");
    }
  }

  async function resolve(decision) {
    if (!proposal || locked.current) return;
    locked.current = true;
    setBusy(decision);
    setError("");
    try {
      const result = await api.resolveAction(proposal.id, decision);
      append("assistant", result.message);
      setProposal(null);
      setCareRevision((value) => value + 1);
    } catch (error) {
      setError(errorMessage(error));
      if ([404, 409, 410].includes(error.status)) {
        setProposal(null);
        setCareRevision((value) => value + 1);
        await restorePending();
      }
    } finally {
      locked.current = false;
      setBusy("");
    }
  }
  return {
    messages,
    proposal,
    busy,
    error,
    failedText,
    send,
    resolve,
    pendingReady,
    pendingError,
    restorePending,
    proposeAppointment,
    careRevision,
  };
}
