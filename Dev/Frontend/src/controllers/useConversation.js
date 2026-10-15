import { useRef, useState } from "react";
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
  const append = (role, text) =>
    setMessages((items) => [...items, { id: crypto.randomUUID(), role, text }]);

  async function send(text, retry = false) {
    const clean = text.trim();
    if (!clean || locked.current || proposal) return false;
    locked.current = true;
    setBusy("thinking");
    setError("");
    setFailedText("");
    if (!retry) append("user", clean);
    try {
      const reply = await api.converse(clean, conversationId.current);
      append("assistant", reply.text);
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

  async function resolve(decision) {
    if (!proposal || locked.current) return;
    locked.current = true;
    setBusy(decision);
    setError("");
    try {
      const result = await api.resolveAction(proposal.id, decision);
      append("assistant", result.message);
      setProposal(null);
    } catch (error) {
      setError(errorMessage(error));
      if ([404, 409, 410].includes(error.status)) setProposal(null);
    } finally {
      locked.current = false;
      setBusy("");
    }
  }
  return { messages, proposal, busy, error, failedText, send, resolve };
}
