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
  const mediaProcessorRef = useRef(null);
  const audioCtxRef = useRef(null);
  const speechBufferRef = useRef("");
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // Flag to track when the bot's response stream ends (generation finished).
  const isBotGeneratingRef = useRef(false);

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
      // Only restart listening AFTER audio playback AND generation stream are done.
      if (realtimeTalking && !isBotGeneratingRef.current) {
        restartListening();
      }
      return;
    }
    isPlayingRef.current = true;
    const audioData = audioQueueRef.current.shift();
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext ||
          window.webkitAudioContext)();
      }
      if (audioCtxRef.current.state === "suspended") {
        await audioCtxRef.current.resume();
      }
      const sampleRate = 24000;
      const length = audioData.byteLength / 2;
      const audioBuffer = audioCtxRef.current.createBuffer(
        1,
        length,
        sampleRate
      );
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
    // 🚨 Final Check: Still use a short delay (e.g., 500ms) to clear any lingering network/service state.
    console.log("Waiting 500ms before restarting listening.");
    setTimeout(() => {
      setIsListening(true);
      setIsProcessing(false);
      console.log("Turn reset. Listening for user.");
    }, 500); // Reduced delay for better UX, relying on audio stream halt for the primary fix.
  };

  const startRealtimeTalk = async () => {
    if (realtimeTalking || isProcessing) {
      stopRealtimeTalk();
      return;
    }

    // Reset conversation state on start
    isBotGeneratingRef.current = false;
    audioQueueRef.current = [];
    isPlayingRef.current = false;

    // 1. Establish WebSocket connection
    const ws = new WebSocket("ws://localhost:8000/ws/realtime-audio");
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    setRealtimeTalking(true);

    ws.onopen = async () => {
      try {
        // 2. Get Media Stream (microphone input)
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        if (!audioCtxRef.current) {
          audioCtxRef.current = new (window.AudioContext ||
            window.webkitAudioContext)({
            sampleRate: 16000,
          });
        }
        if (audioCtxRef.current.state === "suspended") {
          await audioCtxRef.current.resume();
        }

        const source = audioCtxRef.current.createMediaStreamSource(stream);
        const processor = audioCtxRef.current.createScriptProcessor(4096, 1, 1);

        source.connect(processor);
        processor.connect(audioCtxRef.current.destination);

        mediaProcessorRef.current = { stream, processor, source };

        // 3. Audio Processing Loop: Get raw PCM, Resample, Convert to PCM16, Send to WS
        processor.onaudioprocess = async (e) => {
          // 🎯 CORE FIX: Stop sending audio chunks the moment processing starts.
          // Sending audio while Azure is processing or generating is the primary cause of the error.
          if (isProcessing) return;

          try {
            const inputBuffer = e.inputBuffer.getChannelData(0);

            const originalSampleRate = audioCtxRef.current.sampleRate;
            const targetSampleRate = 24000;

            // Resampling logic (16kHz -> 24kHz)
            const decoded = audioCtxRef.current.createBuffer(
              1,
              inputBuffer.length,
              originalSampleRate
            );
            decoded.getChannelData(0).set(inputBuffer);

            const offlineCtx = new OfflineAudioContext(
              1,
              decoded.duration * targetSampleRate,
              targetSampleRate
            );
            const src = offlineCtx.createBufferSource();
            src.buffer = decoded;
            src.connect(offlineCtx.destination);
            src.start(0);
            const resampled = await offlineCtx.startRendering();

            // Convert Float32Array → PCM16
            const float32 = resampled.getChannelData(0);
            const buffer = new ArrayBuffer(float32.length * 2);
            const view = new DataView(buffer);
            for (let i = 0; i < float32.length; i++) {
              const s = Math.max(-1, Math.min(1, float32[i]));
              view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
            }

            const b64 = arrayBufferToBase64(buffer);

            // Send to backend/Azure
            wsRef.current.send(
              JSON.stringify({
                type: "input_audio_buffer.append",
                audio: b64,
              })
            );
          } catch (error) {
            if (error.message.includes("closed")) return;
            console.error("❌ Error processing audio data:", error);
          }
        };

        setIsListening(true); // Start listening state
      } catch (error) {
        console.error("❌ Audio setup error:", error);
        setChats((prev) => {
          const updated = [...prev];
          const lastChat = updated[currentChatIndex];
          lastChat.messages.push({
            user: null,
            bot: {
              type: "text",
              content: `❌ Audio setup error: ${error.message}`,
            },
          });
          return updated;
        });
        stopRealtimeTalk();
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
              // Azure VAD detected end of user speech
              if (!isProcessing) {
                // Send commit to backend to initiate bot response
                wsRef.current?.send(
                  JSON.stringify({ type: "input_audio_buffer.commit" })
                );
                setIsListening(false);
                setIsProcessing(true);
                isBotGeneratingRef.current = true; // Bot turn starts now
                console.log("User finished speaking. Sent commit.");
              } else {
                console.warn("Ignoring speech_stopped: Bot is already active.");
              }
            } else if (data.type === "transcription") {
              setChats((prev) => {
                const updated = [...prev];
                const lastChat = updated[currentChatIndex];
                const lastMessage =
                  lastChat.messages[lastChat.messages.length - 1];
                if (!lastMessage || lastMessage.user !== data.transcript) {
                  lastChat.messages.push({ user: data.transcript, bot: null });
                }
                return updated;
              });
              setTranscriptBuffer("");
              setCurrentTranscription("");
            } else if (data.type === "transcript_delta") {
              setTranscriptBuffer((prev) => {
                const newBuffer = prev + data.delta;
                setCurrentTranscription(newBuffer);
                return newBuffer;
              });
            } else if (data.type === "error") {
              // Handle backend/Azure errors
              setIsProcessing(false);
              isBotGeneratingRef.current = false; // Generation stops on error
              setChats((prev) => {
                const updated = [...prev];
                const lastChat = updated[currentChatIndex];
                lastChat.messages.push({
                  user: null,
                  bot: {
                    type: "text",
                    content: `❌ Backend error: ${data.message}`,
                  },
                });
                return updated;
              });
              // Attempt to restart listening immediately after error
              if (realtimeTalking) {
                restartListening();
              }
            }
          } catch (e) {
            // Plain text message stream or [END]
            if (event.data === "[END]") {
              // Bot generation complete
              if (speechBufferRef.current) {
                setChats((prev) => {
                  const updated = [...prev];
                  const lastChat = updated[currentChatIndex];
                  if (
                    lastChat.messages.length > 0 &&
                    !lastChat.messages[lastChat.messages.length - 1].bot
                  ) {
                    lastChat.messages[lastChat.messages.length - 1].bot = {
                      type: "text",
                      content: speechBufferRef.current,
                    };
                  }
                  return updated;
                });
              }
              speechBufferRef.current = "";
              setIsProcessing(false);

              // Clear bot generating status, allowing playNextAudioChunk to handle final restart.
              isBotGeneratingRef.current = false;
              console.log("Bot generation finished. Waiting for playback end.");

              // If playback queue is already empty, force a restart
              if (
                audioQueueRef.current.length === 0 &&
                !isPlayingRef.current &&
                realtimeTalking
              ) {
                restartListening();
              }
              return;
            }
            // Append text stream data to the speech buffer
            speechBufferRef.current += event.data;
          }
        } else if (event.data instanceof ArrayBuffer) {
          setBinaryMessageCount((prev) => prev + 1);
          playAudioQueued(event.data);
        } else if (event.data instanceof Blob) {
          const arr = await event.data.arrayBuffer();
          setBinaryMessageCount((prev) => prev + 1);
          playAudioQueued(arr);
        }
      } catch (error) {
        console.error("❌ Critical error in message handler:", error);
      }
    };

    ws.onclose = () => {
      setRealtimeTalking(false);
      stopAudioProcessing();
      isBotGeneratingRef.current = false;
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setChats((prev) => {
        const updated = [...prev];
        const lastChat = updated[currentChatIndex];
        lastChat.messages.push({
          user: null,
          bot: {
            type: "text",
            content: "❌ WebSocket connection error. Please try again.",
          },
        });
        return updated;
      });
      stopRealtimeTalk();
    };
  };

  const stopRealtimeTalk = () => {
    if (wsRef.current) wsRef.current.close();
    setRealtimeTalking(false);
    stopAudioProcessing();
  };

  const stopAudioProcessing = () => {
    if (mediaProcessorRef.current) {
      mediaProcessorRef.current.source.disconnect();
      mediaProcessorRef.current.processor.disconnect();
      mediaProcessorRef.current.stream.getTracks().forEach((t) => t.stop());
      mediaProcessorRef.current = null;
      setIsListening(false);
    }
  };

  // --- Standard Chat Functions (Omitted for brevity, assumed unchanged) ---
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
      const normalized =
        typeof botReply === "string"
          ? { type: "text", content: botReply }
          : botReply;
      newChats[currentChatIndex].messages = newChats[
        currentChatIndex
      ].messages.map((m) =>
        m.user === msg && !m.bot ? { user: msg, bot: normalized } : m
      );
      setChats([...newChats]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsTyping(false);
    }
  };

  const startVoice = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition)
      return alert("Your browser does not support voice input");
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

  const newChat = () =>
    setChats([...chats, { name: `Chat #${chats.length + 1}`, messages: [] }]) &&
    setCurrentChatIndex(chats.length);
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
  const clearChat = () => {
    setChats([{ name: "Chat #1", messages: [] }]);
    setCurrentChatIndex(0);
  };
  const exportChat = () => {
    const chat = chats[currentChatIndex];
    const content = chat.messages
      .map(
        (m) =>
          `You: ${m.user}\nBot: ${
            typeof m.bot === "string" ? m.bot : JSON.stringify(m.bot)
          }`
      )
      .join("\n\n");
    const blob = new Blob([content], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${chat.name}.txt`;
    link.click();
  };

  // UI (Unchanged)
  return (
    <div
      className={
        darkMode
          ? "h-screen flex bg-gray-900 text-white"
          : "h-screen flex bg-gray-200 text-black"
      }
    >
      {/* Sidebar */}
      <div
        className={`w-64 p-2 overflow-y-auto ${
          darkMode ? "bg-gray-800 text-white" : "bg-gray-200 text-black"
        }`}
      >
        <div className="flex items-center mb-4">
          <span className="font-bold">Chats</span>
          <button
            onClick={newChat}
            className="ml-auto text-xs text-green-400 hover:text-green-600"
          >
            + New Chat
          </button>
        </div>
        {chats.map((chat, i) => (
          <div
            key={i}
            className={`flex items-center justify-between p-2 mb-1 rounded cursor-pointer ${
              i === currentChatIndex ? "bg-gray-700" : "hover:bg-gray-700"
            }`}
            onClick={() => setCurrentChatIndex(i)}
          >
            <span className="truncate">{chat.name}</span>
            <div className="flex gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  renameChat(i);
                }}
                className="text-xs text-yellow-300 hover:text-yellow-400"
              >
                ✏
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteChat(i);
                }}
                className="text-xs text-red-400 hover:text-red-600"
              >
                🗑
              </button>
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
            <button
              onClick={clearChat}
              className="bg-red-600 px-2 py-1 rounded hover:bg-red-500 text-xs"
            >
              🗑 Clear
            </button>
            <button
              onClick={exportChat}
              className="bg-green-600 px-2 py-1 rounded hover:bg-green-500 text-xs"
            >
              📄 Export
            </button>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="bg-gray-700 px-2 py-1 rounded hover:bg-gray-600 text-xs"
            >
              {darkMode ? "☀" : "🌙"}
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-2">
          {chats[currentChatIndex]?.messages.map((m, i) => (
            <div key={i} className="flex flex-col">
              {m.user && (
                <div className="self-end max-w-2xl bg-gray-700 text-white p-3 rounded-lg rounded-br-none break-words">
                  {m.user}
                </div>
              )}
              {m.bot && (
                <div className="self-start max-w-2xl bg-gray-800 text-white p-3 rounded-lg rounded-bl-none mt-1 break-words">
                  {m.bot.type === "text" && (
                    <ReactMarkdown>{m.bot.content}</ReactMarkdown>
                  )}
                  {m.bot.type === "image" && (
                    <img
                      src={m.bot.content}
                      alt="Chatbot result"
                      style={{ maxWidth: "100%" }}
                    />
                  )}
                </div>
              )}
            </div>
          ))}
          {isTyping && (
            <div className="self-start max-w-2xl bg-gray-800 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">
              Chatbot is typing...
            </div>
          )}
          {listening && (
            <div className="self-start max-w-2xl bg-yellow-500 text-black p-3 rounded-lg rounded-bl-none font-bold">
              🎤 Listening...
            </div>
          )}
          {isListening && (
            <div className="self-start max-w-2xl bg-green-500 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">
              🎤 Listening to you...
            </div>
          )}
          {isProcessing && (
            <div className="self-start max-w-2xl bg-blue-500 text-white p-3 rounded-lg rounded-bl-none font-bold animate-pulse">
              🤖 Processing...
            </div>
          )}
          {currentTranscription && (
            <div className="self-start max-w-2xl bg-purple-500 text-white p-3 rounded-lg rounded-bl-none font-bold">
              📝 "{currentTranscription}"
            </div>
          )}
        </div>

        {/* Input + Buttons */}
        <div className="flex">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            className="flex-1 p-3 rounded-l bg-gray-800 text-white focus:outline-none"
            placeholder="Type a message..."
            disabled={realtimeTalking}
          />
          <button
            onClick={() => sendMessage(input)}
            className="bg-gray-700 p-3 rounded-r hover:bg-gray-600"
            disabled={realtimeTalking}
          >
            Send
          </button>
          <button
            onClick={startVoice}
            className="bg-gray-700 p-3 ml-1 rounded hover:bg-gray-600"
            disabled={realtimeTalking}
          >
            🎤
          </button>
          <button
            onClick={startRealtimeTalk}
            className={`p-3 ml-1 rounded ${
              realtimeTalking
                ? "bg-red-600 hover:bg-red-500"
                : "bg-blue-600 hover:bg-blue-500"
            }`}
            disabled={isProcessing}
          >
            {realtimeTalking
              ? isListening
                ? "🎤 Listening..."
                : isProcessing
                ? "🤖 Processing..."
                : "🛑 Stop"
              : "🎧 Realtime Talk"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
