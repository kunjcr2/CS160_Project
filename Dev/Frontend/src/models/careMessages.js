export const MESSAGE_MAX_LENGTH = 2000;

export function normalizeCareMessages(value) {
  if (!Array.isArray(value) || value.some((row) =>
    !row || typeof row.id !== "string" || !row.id ||
    typeof row.provider?.id !== "string" || !row.provider.id ||
    typeof row.provider?.name !== "string" || !row.provider.name ||
    typeof row.body !== "string" || !row.body.trim() ||
    !["sent", "failed"].includes(row.status) ||
    !Number.isFinite(Date.parse(row.created_at)))) {
    throw new Error("The message history response is incomplete. Please refresh and try again.");
  }
  return [...value].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}
