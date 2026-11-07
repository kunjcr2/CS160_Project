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
MEDICATION_REQUEST_RECEIVED = "I can help set a medication reminder. What medicine and what time should I use?"
AI_UNAVAILABLE = "I can't reach the assistant right now. Please try again."
