```powershell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> @'
>> {"text":"Hello, this is a test of text to speech."}
>> '@ | curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/tts" `
>>   -H "Content-Type: application/json" `
>>   --data-binary "@-" `
>>   --output reply.mp3 `
>>   --write-out "`nHTTP %{http_code}`nType: %{content_type}`nBytes: %{size_download}`n"
  % Total    % Received % Xferd  Average Speed  Time    Time Time   Current
                                 Dload  Upload  Total   Spent Left   Speed
  0      0   0      0   0      0      0      0100     53   0      0 100     53      0     50   00:01   00:01100     53   0      0 100     53      0     25   00:02   00:02100  56117 100  56064 100     53  19000     17   00:03   00:02100  56117 100  56064 100     53  18830     17   00:03   00:02100  56117 100  56064 100     53  18575     17   00:03   00:03            25

HTTP 200
Type: audio/mpeg
Bytes: 56064
```

```poewrshell
PS C:\Users\kunjs\Downloads\Projects\CS160_Project> curl.exe -X POST "http://127.0.0.1:5000/api/v1/ai/transcribe" `
>>   -F "audio=@reply.mp3;type=audio/mp3"
{"text":"Hello, this is a test of text-to-speech."}
```
