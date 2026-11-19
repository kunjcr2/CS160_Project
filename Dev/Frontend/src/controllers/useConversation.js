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
  const unclearTurns = useRef(0);
  const [suggestion, setSuggestion] = useState(null);
  const [pendingReady, setPendingReady] = useState(false);
  const [pendingError, setPendingError] = useState("");
  const [careRevision, setCareRevision] = useState(0);
  const [lastResolution, setLastResolution] = useState(null);
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
    setSuggestion(null);
    if (!retry) append("user", clean);
    try {
      const reply = await api.converse(clean, conversationId.current, unclearTurns.current);
      if (!mounted.current) return false;
      unclearTurns.current = reply.unclearTurns ?? 0;
      setSuggestion(reply.intent || (reply.offerHumanHelp ? { kind: "human_help", reason: "repeated_failures" } : null));
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

  async function propose(createAction) {
    if (locked.current || proposal || !pendingReady) return false;
    locked.current = true;
    setBusy("proposing");
    setSuggestion(null);
    setError("");
    setFailedText("");
    try {
      const action = await createAction();
      if (!mounted.current) return false;
      append("assistant", action.summary);
      setProposal(action);
      return action;
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

  function proposeAppointment(slot) {
    return propose(() => api.proposeAppointment(slot.slot_id));
  }

  function proposeCareMessage(olderAdultId, providerId, body) {
    return propose(() => api.proposeCareMessage(olderAdultId, providerId, body));
  }

  async function resolve(decision) {
    if (!proposal || locked.current) return;
    locked.current = true;
    setBusy(decision);
    setError("");
    try {
      const result = await api.resolveAction(proposal.id, decision, proposal.action_type);
      append("assistant", result.message);
      setLastResolution({ id: proposal.id, actionType: proposal.action_type, status: result.status,
        data: result.data, message: result.message });
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
    proposeCareMessage,
    proposeHumanHelp: (userId, summary, reason) => propose(() => api.proposeHumanHelp(userId, summary, reason)),
    proposeRefill: (userId, medicationId) => propose(() => api.proposeRefill(userId, medicationId)),
    proposeCancellation: (id) => propose(() => api.proposeCancellation(id)),
    proposeReschedule: (id, slotId) => propose(() => api.proposeReschedule(id, slotId)),
    suggestion,
    clearSuggestion: () => setSuggestion(null),
    lastResolution,
    careRevision,
  };
}
