```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"I need an appointment with Dr. Chen next Tuesday.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"I can help you find an appointment. Which doctor should I look for?","proposal":{"kind":"appointment","doctor":"Dr. Chen","date_hint":"next Tuesday"}}
```

```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"Schedule a doctor visit tomorrow.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"I can help you find an appointment. Which doctor should I look for?","proposal":{"kind":"appointment","doctor":null,"date_hint":"tomorrow"}}
```

```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"Remind me to take aspirin at 8 PM.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"I can help set a medication reminder. What medicine and what time should I use?","proposal":{"kind":"medication_reminder","medication":"aspirin","time_hint":"8 PM"}}
```

```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"Set a reminder for my blood pressure medicine every morning.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"I can help set a medication reminder. What medicine and what time should I use?","proposal":{"kind":"medication_reminder","medication":"blood pressure medicine","time_hint":"every morning"}}
```

```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"Tell me a joke.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"Sorry, I didn't understand. Could you say that another way?","proposal":null}
```

```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"User: Set a reminder for my blood pressure medicine every morning. \nAssistant: I can help set a medication reminder. What medicine and what time should I use?\n User: Morning 8 and Dolo.","language":"en"}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/process" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-"
{"reply":"I can help set a medication reminder. What medicine and what time should I use?","proposal":{"kind":"medication_reminder","medication":"Dolo","time_hint":"every morning; Morning 8"}}
```
