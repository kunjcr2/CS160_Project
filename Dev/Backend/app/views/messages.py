"""Every sentence the backend says to the user, in one place (English only for now).

Keep wording short and plain (plan §13); reword freely after usability tests.
Services fill the {placeholders} with str.format(). Multilingual support (PB-05)
is deferred; if it returns, this file becomes the English template set.
"""

# Appointment booking (PB-01)
BOOKING_OPTIONS = "I found these times with {doctor}: {options}. Which one would you like?"
BOOKING_CONFIRM = "{doctor}, {specialty}, {date} at {time}, at {location}. Should I book it?"
BOOKING_DONE = "Done. You're booked with {doctor} on {date} at {time}."
BOOKING_NO_AVAILABILITY = "{doctor} has no open times then. Should I check the next week?"
BOOKING_SLOT_TAKEN = "Sorry, that time was just taken. The next open times are: {options}."
BOOKING_FAILED = "I couldn't book that, and nothing changed. You can call the office at {phone}."

# Appointment reminders (PB-02), keyed by AppointmentReminder.kind
REMINDERS = {
    "day_before": "Reminder: you see {doctor} tomorrow at {time}, at {location}.",
    "morning_of": "Good morning. You see {doctor} today at {time}, at {location}.",
    "hour_before": "Your appointment with {doctor} is in one hour, at {location}.",
}

# Confirmation (plan §5.3)
CONFIRM_UNCLEAR = "I didn't catch a yes or a no. Should I go ahead?"
ACTION_CANCELLED = "Okay, I won't do that."
ACTION_EXPIRED = "That request timed out, so I didn't do anything. We can start again."

# Errors and fallback (plan §7)
NOT_UNDERSTOOD = "Sorry, I didn't understand. Could you say that another way?"
OFFER_HUMAN_HELP = "I'm having trouble with this. Would you like me to connect you with a person?"
SERVICE_UNAVAILABLE = "Something went wrong on my end, and nothing was changed. Please try again."

# Conversation (SR-08). These replies accompany proposals only; another controller
# will persist and confirm any action before it can be carried out.
APPOINTMENT_REQUEST_RECEIVED = "I can help you find an appointment. Which doctor should I look for?"
MEDICATION_REQUEST_RECEIVED = (
    "I can help set a medication reminder. What medicine and what time should I use?"
)
AI_UNAVAILABLE = "I can't reach the assistant right now. Please try again."

# Voice conversation and proposal read-backs. A read-back checks recognition;
# it does not confirm or execute a pending action.
CONVERSATION = {
    "en": {
        "appointment_missing_doctor": "Which doctor would you like to see?",
        "appointment_missing_date": "What day would you like the appointment?",
        "appointment_ready": "I can look for that appointment. Please verify the details.",
        "appointment_readback": (
            "I heard an appointment with {doctor} on {date_hint}. Is that right?"
        ),
        "medication_missing_name": "Which medicine should I remind you about?",
        "medication_missing_time": "What time should I remind you about {medication}?",
        "medication_ready": "I can help set that reminder. Please verify the details.",
        "medication_readback": "I heard a reminder for {medication} at {time_hint}. Is that right?",
        "refill_missing_name": "Which medicine needs a refill?",
        "refill_ready": "I can help with that refill. Please verify the medicine.",
        "refill_readback": "I heard a refill request for {medication}. Is that right?",
        "human_help": "I can request help from a person. Would you like me to do that?",
        "human_help_requested": (
            "I can prepare a request for a person. Please confirm before sending it."
        ),
        "not_understood": NOT_UNDERSTOOD,
        "offer_human_help": OFFER_HUMAN_HELP,
    },
    "es": {
        "appointment_missing_doctor": "¿Con qué médico quiere una cita?",
        "appointment_missing_date": "¿Qué día quiere la cita?",
        "appointment_ready": "Puedo buscar esa cita. Confirme los detalles.",
        "appointment_readback": "Entendí una cita con {doctor} el {date_hint}. ¿Es correcto?",
        "medication_missing_name": "¿De qué medicamento quiere un recordatorio?",
        "medication_missing_time": "¿A qué hora quiere el recordatorio de {medication}?",
        "medication_ready": "Puedo ayudarle con ese recordatorio. Confirme los detalles.",
        "medication_readback": (
            "Entendí un recordatorio de {medication} a las {time_hint}. ¿Es correcto?"
        ),
        "refill_missing_name": "¿Qué medicamento necesita resurtir?",
        "refill_ready": "Puedo ayudarle con ese resurtido. Confirme el medicamento.",
        "refill_readback": "Entendí un resurtido de {medication}. ¿Es correcto?",
        "human_help": "Puedo pedir ayuda a una persona. ¿Quiere que lo haga?",
        "human_help_requested": (
            "Puedo preparar una solicitud de ayuda. Confírmela antes de enviarla."
        ),
        "not_understood": "Perdón, no entendí. ¿Puede decirlo de otra manera?",
        "offer_human_help": "Me está costando entender. ¿Quiere que le ayude una persona?",
    },
}


def say(key: str, language: str, **values: str) -> str:
    return CONVERSATION.get(language, CONVERSATION["en"])[key].format(**values)
