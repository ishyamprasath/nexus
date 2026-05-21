import React, { useState, useRef, useEffect } from 'react';
import { Send, Menu, X, Plus } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! How can I help you today?'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleNewChat = () => {
    setMessages([
      {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Hello! How can I help you today?'
      }
    ]);
    setInputValue('');
    setIsSidebarOpen(false);
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const userText = inputValue.trim();
    setInputValue('');

    // Add user message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userText
    };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      // Connect to the backend
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userText,
          history: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });

      const data = await response.json();

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response || data.text || 'Sorry, I encountered an error.'
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '**Error:** Could not connect to the backend. Is it running?'
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-screen w-full bg-[#212121] text-gray-100 font-sans overflow-hidden">
      
      {/* Sidebar toggle button (Mobile) */}
      <button 
        onClick={() => setIsSidebarOpen(true)}
        className="md:hidden fixed left-4 top-4 z-20 p-2 rounded-md bg-[#2f2f2f] text-gray-300 hover:text-white"
      >
        <Menu size={20} />
      </button>

      {/* Sidebar */}
      <aside className={`fixed md:relative z-30 h-full w-[260px] bg-[#171717] flex flex-col transition-transform duration-300 ease-in-out ${
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      }`}>
        <div className="p-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold">Nexus AI</h1>
          <button 
            onClick={() => setIsSidebarOpen(false)}
            className="md:hidden p-1 text-gray-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        <div className="px-3 pb-3">
          <button 
            onClick={handleNewChat}
            className="w-full flex items-center gap-2 px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
          >
            <Plus size={18} />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2 text-sm text-gray-400">
          <p className="px-2 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">Today</p>
          <button className="w-full text-left px-3 py-2 rounded-lg bg-[#2f2f2f] text-gray-200 truncate">
            General Chat
          </button>
        </div>
      </aside>

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <div 
          onClick={() => setIsSidebarOpen(false)}
          className="md:hidden fixed inset-0 bg-black/50 z-20"
        />
      )}

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col relative h-full bg-[#212121]">
        
        {/* Messages container */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col gap-6">
          <div className="max-w-3xl w-full mx-auto flex flex-col gap-6 pt-10 pb-32">
            {messages.map((m) => (
              <div 
                key={m.id} 
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-5 py-3.5 text-[15px] leading-relaxed ${
                  m.role === 'user' 
                    ? 'bg-[#2f2f2f] text-white rounded-br-sm' 
                    : 'bg-transparent text-gray-100'
                }`}>
                  {m.role === 'assistant' && (
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-[10px] font-bold text-white shrink-0">
                        AI
                      </div>
                      <span className="font-semibold text-sm">Nexus</span>
                    </div>
                  )}
                  
                  <div className={`whitespace-pre-wrap ${m.role === 'assistant' ? 'pl-9' : ''}`}>
                    {m.content}
                  </div>
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div className="flex justify-start">
                <div className="max-w-[85%] px-5 py-3 text-gray-400 flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-blue-600/50 flex items-center justify-center shrink-0">
                    <span className="w-1 h-1 bg-white rounded-full animate-bounce"></span>
                  </div>
                  <span className="text-sm animate-pulse">Nexus is typing...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Chat Input */}
        <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-[#212121] via-[#212121] to-transparent pt-10 pb-6 px-4">
          <div className="max-w-3xl mx-auto relative flex items-center bg-[#2f2f2f] rounded-2xl shadow-xl border border-white/5 focus-within:border-white/20 transition-colors">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Nexus..."
              className="w-full bg-transparent text-gray-100 placeholder-gray-500 rounded-2xl px-5 py-4 outline-none resize-none min-h-[56px] max-h-[200px]"
              rows={1}
            />
            <button 
              onClick={handleSend}
              disabled={!inputValue.trim() || isTyping}
              className={`absolute right-3 p-2 rounded-xl transition-all ${
                inputValue.trim() && !isTyping
                  ? 'bg-blue-600 text-white hover:bg-blue-500' 
                  : 'bg-white/5 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Send size={18} />
            </button>
          </div>
          <div className="text-center mt-3 text-xs text-gray-500">
            Nexus AI can make mistakes. Consider verifying important information.
          </div>
        </div>
      </main>
    </div>
  );
}
