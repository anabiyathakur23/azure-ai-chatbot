import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import "./index.css";

function App() {
  const [chats, setChats] = useState([{ name: "Chat #1", messages: [] }]);
  const [currentChatIndex, setCurrentChatIndex] = useState(0);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [realtimeTalking, setRealtimeTalking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentTranscription, setCurrentTranscription] = useState("");
  const [transcriptBuffer, setTranscriptBuffer] = useState("");
  const [binaryMessageCount, setBinaryMessageCount] = useState(0);

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioCtxRef = useRef(null);
  const speechBufferRef = useRef("");
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // PCM16 playback queue (mono, 24000Hz)
  const playAudioQueued = (audioData) => {
    audioQueueRef.current.push(audioData);
    if (!isPlayingRef.current) {
      playNextAudioChunk();
    }
  };

  const playNextAudioChunk = async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      // After all audio played, restart listening for next user turn
      if (realtimeTalking) restartListening();
      return;
    }
    isPlayingRef.current = true;
    const audioData = audioQueueRef.current.shift();
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtxRef.current.state === "suspended") {
        await audioCtxRef.current.resume();
      }
      const sampleRate = 24000;
      const length = audioData.byteLength / 2;
      const audioBuffer = audioCtxRef.current.createBuffer(1, length, sampleRate);
      const channelData = audioBuffer.getChannelData(0);
      const view = new DataView(audioData);
      for (let i = 0; i < length; i++) {
        channelData[i] = view.getInt16(i * 2, true) / 32768;
      }
      const source = audioCtxRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtxRef.current.destination);
      source.onended = () => {
        playNextAudioChunk();
      };
      source.start();
    } catch (err) {
      console.error("❌ playAudio error:", err);
      isPlayingRef.current = false;
    }
  };

  // Convert Float32Array to PCM16
  const floatTo16BitPCM = (float32Array) => {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buffer;
  };

  const arrayBufferToBase64 = (buffer) => {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode.apply(null, chunk);
    }
    return btoa(binary);
  };

  // --- Realtime Talk ---
  const restartListening = () => {
    // Start MediaRecorder for next user input
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "recording") {
      mediaRecorderRef.current.start(100);
      setIsListening(true);
      setIsProcessing(false);
    }
  };

  const startRealtimeTalk = async () => {
    if (realtimeTalking) {
      stopRealtimeTalk();
      return;
    }
    const ws = new WebSocket("ws://localhost:8000/ws/realtime-audio");
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    setRealtimeTalking(true);

    ws.onopen = async () => {
      try {
        if (!audioCtxRef.current) {
          audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm;codecs=opus'
        });
        mediaRecorderRef.current = mediaRecorder;
        mediaRecorder.ondataavailable = async (e) => {
          try {
            if (e.data.size > 0) {
              const arrayBuffer = await e.data.arrayBuffer();
              const audioBuffer = await audioCtxRef.current.decodeAudioData(arrayBuffer);
              const channelData = audioBuffer.getChannelData(0);
              const pcm16 = floatTo16BitPCM(channelData);
              const b64 = arrayBufferToBase64(pcm16);
              wsRef.current.send(JSON.stringify({
                type: "input_audio_buffer",
                audio: b64
              }));
            }
          } catch (error) {
            console.error("❌ Error processing audio data:", error);
          }
        };
        mediaRecorder.onerror = (e) => {
          console.error("❌ MediaRecorder error:", e);
        };
        mediaRecorder.onstart = () => {
          setIsListening(true);
        };
        mediaRecorder.onstop = () => {
          setIsListening(false);
        };
        mediaRecorder.start(100);
      } catch (error) {
        setChats((prev) => {
          const updated = [...prev];
          const lastChat = updated[currentChatIndex];
          lastChat.messages.push({
            user: null,
            bot: { type: "text", content: `❌ Audio setup error: ${error.message}` }
          });
          return updated;
        });
      }
    };

    ws.onmessage = async (event) => {
      try {
        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "speech_started") {
              setIsListening(true);
              setIsProcessing(false);
            } else if (data.type === "speech_stopped") {
              setIsListening(false);
              setIsProcessing(true);
            } else if (data.type === "transcription") {
              setChats((prev) => {
                const updated = [...prev];
                const lastChat = updated[currentChatIndex];
                const lastMessage = lastChat.messages[lastChat.messages.length - 1];
                if (!lastMessage || lastMessage.user !== data.transcript) {
                  lastChat.messages.push({ user: data.transcript, bot: null });
                }
                return updated;
              });
              setTranscriptBuffer("");
              setCurrentTranscription("");
            } else if (data.type === "transcript_delta") {
              setTranscriptBuffer(prev => {
                const newBuffer = prev + data.delta;
                setCurrentTranscription(newBuffer);
                return newBuffer;
              });
            } else if (data.type === "error") {
              setIsProcessing(false);
              setChats((prev) => {
                const updated = [...prev];
                const lastChat = updated[currentChatIndex];
                lastChat.messages.push({
                  user: null,
                  bot: { type: "text", content: `❌ Backend error: ${data.message}` }
                });
                return updated;
              });
            }
          } catch (e) {
            if (event.data === "[END]") {
              if (speechBufferRef.current) {
                setChats((prev) => {
                  const updated = [...prev];
                  const lastChat = updated[currentChatIndex];
                  if (lastChat.messages.length > 0 && !lastChat.messages[lastChat.messages.length - 1].bot) {
                    lastChat.messages[lastChat.messages.length - 1].bot = {
                      type: "text",
                      content: speechBufferRef.current
                    };
                  }
                  return updated;
                });
              }
              speechBufferRef.current = "";
              setIsProcessing(false);
              // Bot turn done: restart listening
              if (realtimeTalking) restartListening();
              return;
            }
            speechBufferRef.current += event.data;
          }
        } else if (event.data instanceof ArrayBuffer) {
          setBinaryMessageCount(prev => prev + 1);
          playAudioQueued(event.data);
        } else if (event.data instanceof Blob) {
          const arr = await event.data.arrayBuffer();
          setBinaryMessageCount(prev => prev + 1);
          playAudioQueued(arr);
        }
      } catch (error) {
        console.error("❌ Critical error in message handler:", error);
      }
    };

    ws.onclose = () => {
      setRealtimeTalking(false);
      setIsListening(false);
      setIsProcessing(false);
      stopMediaRecorder();
    };

    ws.onerror = (error) => {
      setChats((prev) => {
        const updated = [...prev];
        const lastChat = updated[currentChatIndex];
        lastChat.messages.push({
          user: null,
          bot: { type: "text", content: "❌ WebSocket connection error. Please try again." }
        });
        return updated;
      });
      setRealtimeTalking(false);
      setIsListening(false);
      setIsProcessing(false);
    };
  };

  const stopRealtimeTalk = () => {
    if (wsRef.current) wsRef.current.close();
    setRealtimeTalking(false);
    stopMediaRecorder();
  };

  const stopMediaRecorder = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
      mediaRecorderRef.current = null;
    }
  };

  // Text Chat Send
  const sendMessage = async (msg) => {
    if (!msg) return;
    const newChats = [...chats];
    newChats[currentChatIndex].messages.push({ user: msg, bot: null });
    setChats(newChats);
    setInput("");
    setIsTyping(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const data = await response.json();
      const botReply = data.reply;
      const normalized = typeof botReply === "string" ? { type: "text", content: botReply } : botReply;
      newChats[currentChatIndex].messages = newChats[currentChatIndex].messages.map((m) =>
        m.user === msg && !m.bot ? { user: msg, bot: normalized } : m
      );
      setChats([...newChats]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsTyping(false);
    }
  };

  // Voice Input (Non-Realtime)
  const startVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Your browser does not support voice input");
    setListening(true);
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (e) => {
      const spokenText = e.results[0][0].transcript;
      setListening(false);
      setInput(spokenText);
      sendMessage(spokenText);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognition.start();
  };

  // Chat Management
  const newChat = () => setChats([...chats, { name: `Chat #${chats.length + 1}`, messages: [] }]) && setCurrentChatIndex(chats.length);
  const renameChat = (i) => {
    const newName = prompt("Enter new chat name:", chats[i].name);
    if (!newName) return;
    const updated = [...chats];
    updated[i].name = newName;
    setChats(updated);
  };
  const deleteChat = (i) => {
    if (!window.confirm("Are you sure?")) return;
    const updated = chats.filter((_, idx) => idx !== i);
    setChats(updated);
    setCurrentChatIndex(Math.max(0, currentChatIndex - 1));
  };
  const clearChat = () => { setChats([{ name: "Chat #1", messages: [] }]); setCurrentChatIndex(0); };
  const exportChat = () => {
    const chat = chats[currentChatIndex];
    const content = chat.messages
      .map((m) => `You: ${m.user}\nBot: ${typeof m.bot === "string" ? m.bot : JSON.stringify(m.bot)}`)
      .join("\n\n");
    const blob = new Blob([content], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${chat.name}.txt`;
    link.click();
  };

  // UI
  return (
    <div className={darkMode ? "h-screen flex bg-gray-900 text-white" : "h-screen flex bg-gray-200 text-black"}>
      {/* Sidebar */}
      <div className={`w-64 p-2 overflow-y-auto ${darkMode ? "bg-gray-800 text-white" : "bg-gray-200 text-black"}`}>
        <div className="flex items-center mb-4">
          <span className="font-bold">Chats</span>
          <button onClick={newChat} className="ml-auto text-xs text-green-400 hover:text-green-600">+ New Chat</button>
        </div>
        {chats.map((chat, i) => (
          <div key={i} className={`flex items-center justify-between p-2 mb-1 rounded cursor-pointer ${i === currentChatIndex ? "bg-gray-700" : "hover:bg-gray-700"}`} onClick={() => setCurrentChatIndex(i)}>
            <span className="truncate">{chat.name}</span>
            <div className="flex gap-1">
              <button onClick={(e) => { e.stopPropagation(); renameChat(i); }} className="text-xs text-yellow-300 hover:text-yellow-400">✏️</button>
              <button onClick={(e) => { e.stopPropagation(); deleteChat(i); }} className="text-xs text-red-400 hover:text-red-600">🗑️</button>
            </div>
          </div>
        ))}
      </div>

      {/* Chat Panel */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden">
        {/* Header */}
        <div className="h-12 flex items-center justify-between px-4 bg-gray-800 mb-2 shadow-md">
          <span className="font-bold text-lg">CHATBOT</span>
          <div className="flex gap-2">
            <button onClick={clearChat} className="bg-red-600 px-2 py-1 rounded hover:bg-red-500 text-xs">🗑️ Clear</button>
            <button onClick={exportChat} className="bg-green-600 px-2 py-1 rounded hover:bg-green-500 text-xs">📄 Export</button>
            <button onClick={() => setDarkMode(!darkMode)} className="bg-gray-700 px-2 py-1 rounded hover:bg-gray-600 text-xs">{darkMode ? "☀️" : "🌙"}</button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-2">
          {chats[currentChatIndex]?.messages.map((m, i) => (
            <div key={i} className="flex flex-col">
              {m.user && <div className="self-end max-w-2xl bg-gray-700 text-white p-3 rounded-lg rounded-br-none break-words">{m.user}</div>}
              {m.bot && (
                <div className="self-start max-w-2xl bg-gray-800 text-white p-3 rounded-lg rounded-bl-none mt-1 break-words">
                  {m.bot.type === "text" && <ReactMarkdown>{m.bot.content}</ReactMarkdown>}
                  {m.bot.type === "image" && (
                    <img src={m.bot.content} alt="Chatbot result" style={{ maxWidth: "100%" }} />
                  )}
                </div>
              )}
            </div>
          ))}
          {isTyping && <div className="self-start max-w-2xl bg-gray-800 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">Chatbot is typing...</div>}
          {listening && <div className="self-start max-w-2xl bg-yellow-500 text-black p-3 rounded-lg rounded-bl-none font-bold">🎤 Listening...</div>}
          {isListening && <div className="self-start max-w-2xl bg-green-500 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">🎤 Listening to you...</div>}
          {isProcessing && <div className="self-start max-w-2xl bg-blue-500 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">🤖 Processing...</div>}
          {currentTranscription && <div className="self-start max-w-2xl bg-purple-500 text-white p-3 rounded-lg rounded-bl-none font-bold">📝 "{currentTranscription}"</div>}
        </div>

        {/* Input + Buttons */}
        <div className="flex">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            className="flex-1 p-3 rounded-l bg-gray-800 text-white focus:outline-none"
            placeholder="Type a message..."
          />
          <button onClick={() => sendMessage(input)} className="bg-gray-700 p-3 rounded-r hover:bg-gray-600">Send</button>
          <button onClick={startVoice} className="bg-gray-700 p-3 ml-1 rounded hover:bg-gray-600">🎤</button>
          <button
            onClick={startRealtimeTalk}
            className={`p-3 ml-1 rounded ${realtimeTalking ? "bg-red-600 hover:bg-red-500" : "bg-blue-600 hover:bg-blue-500"}`}
            disabled={isProcessing}
          >
            {realtimeTalking ? (
              isListening ? "🎤 Listening..." :
                isProcessing ? "🤖 Processing..." :
                  "🛑 Stop"
            ) : "🎧 Realtime Talk"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
