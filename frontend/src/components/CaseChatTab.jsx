import React, { useState, useRef, useEffect } from 'react';
import { Send, CornerDownLeft, ShieldCheck, Quote, ChevronDown, ChevronUp, Sparkles, User, FileText } from 'lucide-react';
import { askQuestion } from '../services/api';

const QUICK_QUESTIONS = [
  "Quelle est la décision finale et le dispositif retenu ?",
  "Quelles sont les demandes et prétentions du demandeur ?",
  "Le Tribunal a-t-il accordé une indemnité au titre de l'article 700 CPC ?",
  "Quels sont les dépens et montants de condamnation ?",
];

export default function CaseChatTab({ affaireId, onSelectChunk }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Bonjour. Je suis votre assistant juridique pour l'analyse de cette décision du Tribunal judiciaire de Paris. Posez vos questions juridiques ou factuelles : chaque affirmation est strictement adossée aux motifs réels du jugement avec citation des passages sources.",
      sources: []
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (questionText) => {
    const q = (questionText || input).trim();
    if (!q || loading) return;

    setInput('');
    const userMsg = { role: 'user', content: q };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await askQuestion(affaireId, q);
      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || []
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (data.sources && data.sources.length > 0 && onSelectChunk) {
        onSelectChunk(data.sources[0]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Erreur de communication avec le pipeline RAG : ${err.message || 'Serveur indisponible.'}`,
          sources: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSource = (msgIndex, sourceIndex, chunkObj) => {
    const key = `${msgIndex}-${sourceIndex}`;
    setExpandedSources((prev) => ({ ...prev, [key]: !prev[key] }));
    if (onSelectChunk && chunkObj) {
      onSelectChunk(chunkObj);
    }
  };

  return (
    <div className="flex flex-col h-[560px] bg-white rounded-lg shadow-subtle border border-paper-300 overflow-hidden">
      
      {/* Grounding Header Strip */}
      <div className="px-5 py-2.5 bg-paper-100 border-b border-paper-200 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-court-emerald" />
          <span className="font-mono text-[11px] font-semibold text-ink-800">
            Cloisonnement Intra-Affaire (ChromaDB)
          </span>
        </div>
        <span className="text-[11px] text-ink-400 font-mono">
          Strictement vérifié sans hallucination
        </span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((m, mIdx) => (
          <div
            key={mIdx}
            className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'} space-y-1.5`}
          >
            {/* Sender Label */}
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-ink-400 px-1">
              {m.role === 'user' ? (
                <span>Avocat / Juriste</span>
              ) : (
                <span className="text-court-navy font-semibold flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-court-emerald" />
                  JurisConsult Assistant
                </span>
              )}
            </div>

            {/* Bubble / Card */}
            <div className={`max-w-[90%] sm:max-w-[85%] rounded-lg p-4 space-y-3 ${
              m.role === 'user'
                ? 'bg-ink-900 text-paper-50 shadow-subtle'
                : 'bg-paper-50 border border-paper-300 text-ink-900 shadow-subtle'
            }`}>
              
              {/* Message Content */}
              <p className={`text-xs sm:text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === 'assistant' ? 'font-serif-legal text-ink-850' : 'font-sans'
              }`}>
                {m.content}
              </p>

              {/* Citations & Sources (Footnotes) */}
              {m.sources && m.sources.length > 0 && (
                <div className="pt-3 border-t border-paper-200 space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono text-ink-500">
                    <span className="flex items-center gap-1 font-semibold text-ink-800">
                      <Quote className="h-3 w-3 text-court-crimson" />
                      Sources judiciaires citées ({m.sources.length}) :
                    </span>
                    <span className="text-[10px] text-ink-400">
                      Cliquer pour inspecter
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    {m.sources.map((s, sIdx) => {
                      const isExpanded = !!expandedSources[`${mIdx}-${sIdx}`];
                      return (
                        <div
                          key={sIdx}
                          className="rounded border border-paper-300 bg-white p-2 text-xs transition-colors"
                        >
                          <div
                            onClick={() => toggleSource(mIdx, sIdx, s)}
                            className="flex items-center justify-between cursor-pointer text-ink-700 hover:text-ink-950"
                          >
                            <span className="font-mono text-[11px] font-medium flex items-center gap-1.5 text-court-crimson">
                              <FileText className="h-3 w-3" />
                              <span>[SOURCE #{sIdx + 1} — Chunk #{s.chunk_index}]</span>
                            </span>
                            {isExpanded ? (
                              <ChevronUp className="h-3 w-3 text-ink-400" />
                            ) : (
                              <ChevronDown className="h-3 w-3 text-ink-400" />
                            )}
                          </div>

                          {isExpanded && (
                            <p className="mt-2 text-xs font-serif-legal text-ink-800 leading-relaxed pl-2.5 border-l-2 border-ink-900 italic bg-paper-50/50 py-1">
                              « {s.text} »
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-ink-400 font-mono py-2">
            <div className="h-2 w-2 rounded-full bg-court-brass animate-ping" />
            <span>Recherche des motifs pertinents et synthèse par Llama 3.2...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Legal Prompts */}
      <div className="px-4 py-2 bg-paper-100 border-t border-paper-200 flex items-center gap-1.5 overflow-x-auto text-xs no-scrollbar">
        <span className="text-ink-400 font-mono text-[10px] shrink-0 uppercase tracking-wider">
          Suggestions :
        </span>
        {QUICK_QUESTIONS.map((q, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSend(q)}
            disabled={loading}
            className="px-2.5 py-1 rounded bg-white hover:bg-paper-200 hover:border-ink-400 text-ink-700 shrink-0 text-[11px] transition-colors border border-paper-300 font-sans"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="p-3 bg-white border-t border-paper-300 flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Interroger cette décision (ex: Le juge a-t-il retenu la faute du gardien ?)..."
          className="flex-1 px-3.5 py-2 bg-paper-50/70 border border-paper-400 rounded text-ink-900 placeholder-ink-400 focus:outline-none focus:bg-white focus:border-ink-900 focus:ring-1 focus:ring-ink-900 text-xs sm:text-sm"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="p-2.5 bg-ink-900 hover:bg-ink-800 disabled:opacity-40 text-paper-50 rounded transition-colors shadow-subtle shrink-0"
          title="Envoyer la question"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </form>

    </div>
  );
}
