import { useState, useRef } from "react";
import "./index.css";

function App() {
  const [chats, setChats] = useState([{ name: "Chat #1", messages: [] }]);
  const [currentChatIndex, setCurrentChatIndex] = useState(0);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const recognitionRef = useRef(null);

  const sendMessage = async (msg) => {
    if (!msg) return;

    const newChats = [...chats];

    // Add user message
    newChats[currentChatIndex].messages.push({ user: msg, bot: "" });

    // Automatically rename chat if it's the first message
    if (newChats[currentChatIndex].messages.length === 1) {
      newChats[currentChatIndex].name = msg.length > 20 ? msg.slice(0, 20) + "..." : msg;
    }

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

      newChats[currentChatIndex].messages = newChats[currentChatIndex].messages.map(
        (m) => (m.user === msg && m.bot === "" ? { user: msg, bot: botReply } : m)
      );
      setChats([...newChats]);
    } catch (err) {
      console.error(err);
      newChats[currentChatIndex].messages = newChats[currentChatIndex].messages.map(
        (m) => (m.user === msg && m.bot === "" ? { user: msg, bot: "Error" } : m)
      );
      setChats([...newChats]);
    } finally {
      setIsTyping(false);
    }
  };

  const startVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Your browser does not support voice input");
      return;
    }

    setListening(true);
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const spokenText = event.results[0][0].transcript;
      setListening(false);
      setInput(spokenText);
      sendMessage(spokenText);
    };

    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    recognition.start();
    recognitionRef.current = recognition;
  };

  const newChat = () => {
    const name = `Chat #${chats.length + 1}`;
    setChats([...chats, { name, messages: [] }]);
    setCurrentChatIndex(chats.length);
    setInput("");
  };

  const renameChat = (index) => {
    const newName = prompt("Enter new chat name:", chats[index].name);
    if (!newName) return;
    const updatedChats = [...chats];
    updatedChats[index].name = newName;
    setChats(updatedChats);
  };

  const deleteChat = (index) => {
    if (!window.confirm("Are you sure you want to delete this chat?")) return;
    const updatedChats = chats.filter((_, i) => i !== index);
    setChats(updatedChats);
    setCurrentChatIndex(Math.max(0, currentChatIndex - 1));
  };

  return (
    <div className="h-screen flex bg-gray-900 text-white">
      {/* Sidebar */}
      <div className="w-64 bg-gray-800 p-2 overflow-y-auto">
        <div className="flex items-center mb-4">
          <span className="font-bold">Chats</span>
          <button
            onClick={newChat}
            className="ml-auto text-xs text-green-400 hover:text-green-600"
          >
            + New Chat
          </button>
        </div>
        {chats.map((chat, index) => (
          <div
            key={index}
            className={`flex items-center justify-between p-2 mb-1 rounded cursor-pointer ${
              index === currentChatIndex ? "bg-gray-700" : "hover:bg-gray-700"
            }`}
            onClick={() => setCurrentChatIndex(index)}
          >
            <span className="truncate">{chat.name}</span>
            <div className="flex gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  renameChat(index);
                }}
                className="text-xs text-yellow-300 hover:text-yellow-400"
              >
                ✏️
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteChat(index);
                }}
                className="text-xs text-red-400 hover:text-red-600"
              >
                🗑️
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Chat panel */}
      <div className="flex-1 flex flex-col p-4 overflow-hidden">
        {/* Chat title */}
        <div className="h-12 flex items-center px-4 bg-gray-800 mb-2 shadow-md">
          <span className="font-bold text-lg">CHATBOT</span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-2">
          {chats[currentChatIndex]?.messages.map((m, i) => (
            <div key={i} className="flex flex-col">
              <div className="self-end max-w-2xl bg-gray-700 text-white p-3 rounded-lg rounded-br-none break-words">
                {m.user}
              </div>
              {m.bot && (
                <div className="self-start max-w-2xl bg-gray-800 text-white p-3 rounded-lg rounded-bl-none mt-1 break-words">
                  {m.bot}
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
        </div>

        {/* Input */}
        <div className="flex">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            className="flex-1 p-3 rounded-l bg-gray-800 text-white focus:outline-none"
            placeholder="Type a message..."
          />
          <button
            onClick={() => sendMessage(input)}
            className="bg-gray-700 p-3 rounded-r hover:bg-gray-600"
          >
            Send
          </button>
          <button
            onClick={startVoice}
            className="bg-gray-700 p-3 ml-1 rounded hover:bg-gray-600"
          >
            🎤
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
