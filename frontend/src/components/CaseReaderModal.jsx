import React, { useState, useEffect, useRef } from 'react';
import { 
  X, ExternalLink, Send, Sparkles, BookOpen, MessageSquare, 
  Download, Check, Bookmark, Calendar, Briefcase, Quote, 
  ShieldCheck, ChevronRight, CornerDownLeft, RefreshCw, AlertCircle
} from 'lucide-react';
import { getCaseDetail, getSummary, askQuestion } from '../services/api';
import AgentTracePanel from './AgentTracePanel';

export default function CaseReaderModal({ caseItem, onClose }) {
  const [fullText, setFullText] = useState('');
  const [textLoading, setTextLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  // Chatbot state
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Highlighting & Active tab in right panel ('summary' | 'chat')
  const [activeTab, setActiveTab] = useState('summary');
  const [activeSourceText, setActiveSourceText] = useState(null);
  const [memoCopied, setMemoCopied] = useState(false);

  const leftTextContainerRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Close on ESC key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Load case details (full text) & summary on mount
  useEffect(() => {
    if (!caseItem?.id) return;

    // Initial message in chat
    setMessages([
      {
        role: 'assistant',
        content: `Bonjour. Je suis l'assistant dédié à cette décision du Tribunal de Paris. Posez vos questions juridiques : chaque réponse sera directement sourcée et le passage officiel sera surligné dans le texte à gauche.`,
        sources: []
      }
    ]);

    loadFullText();
    loadSummary();
  }, [caseItem?.id]);

  const loadFullText = async () => {
    setTextLoading(true);
    try {
      const data = await getCaseDetail(caseItem.id);
      setFullText(data.text || caseItem.text || 'Texte intégral non disponible pour cette décision.');
    } catch (err) {
      setFullText(caseItem.text || 'Texte intégral non disponible.');
    } finally {
      setTextLoading(false);
    }
  };

  const loadSummary = async (forceRefresh = false) => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await getSummary(caseItem.id, forceRefresh);
      setSummary(data);
    } catch (err) {
      setSummaryError(err.message || 'Erreur lors de la génération de la synthèse.');
    } finally {
      setSummaryLoading(false);
    }
  };

  // Scroll to citation highlight when activeSourceText updates
  useEffect(() => {
    if (activeSourceText) {
      const timer = setTimeout(() => {
        const el = document.getElementById('active-citation');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [activeSourceText]);

  // Chat scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatLoading]);

  // Handle chatbot question submission
  const handleSendChat = async (e) => {
    if (e) e.preventDefault();
    const q = chatInput.trim();
    if (!q || chatLoading) return;

    setChatInput('');
    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setChatLoading(true);

    // Switch right panel to chat tab automatically if in summary tab
    setActiveTab('chat');

    try {
      const data = await askQuestion(caseItem.id, q);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources || [],
          agentTrace: data.agent_trace || [],
          metrics: data.metrics || null,
          verificationStatus: data.verification_status || 'SUFFISANT'
        }
      ]);

      // Highlight the first CORPUS_TP2 source passage in the left full text panel!
      const corpusSources = (data.sources || []).filter((s) => s.source_type !== 'SOURCE_EXTERNE');
      if (corpusSources.length > 0) {
        setActiveSourceText(corpusSources[0].text);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Erreur : ${err.message || 'Impossible de joindre le serveur RAG.'}`,
          sources: []
        }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // Fonction d'extraction et de déduplication stricte des questions/réponses (anti-doublon)
  const getDeduplicatedQA = (msgList) => {
    const pairs = [];
    const seen = new Set();

    for (let i = 0; i < msgList.length; i++) {
      if (msgList[i].role === 'user') {
        const q = msgList[i].content.trim();
        let a = '';
        let sources = [];
        let agentTrace = [];
        let metrics = null;
        let verificationStatus = 'SUFFISANT';
        if (i + 1 < msgList.length && msgList[i + 1].role === 'assistant') {
          a = msgList[i + 1].content.trim();
          sources = msgList[i + 1].sources || [];
          agentTrace = msgList[i + 1].agentTrace || [];
          metrics = msgList[i + 1].metrics || null;
          verificationStatus = msgList[i + 1].verificationStatus || 'SUFFISANT';
        }

        // Clé composite stricte de déduplication (insensible à la casse sur la question)
        const key = `${q.toLowerCase()}:::${a}`;
        if (!seen.has(key) && q.length > 0) {
          seen.add(key);
          pairs.push({
            id: `qa-${pairs.length + 1}`,
            index: pairs.length + 1,
            question: q,
            answer: a || "En cours de génération...",
            sources,
            agentTrace,
            metrics,
            verificationStatus,
            date: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
          });
        }
      }
    }
    return pairs;
  };

  // Export complet en .md : Synthèse + Historique dédupliqué des questions/réponses
  const handleExportMemo = () => {
    const qaList = getDeduplicatedQA(messages);

    let qaSlices = [];
    if (qaList.length > 0) {
      qaSlices = [
        `\n---\n`,
        `## IV. HISTORIQUE DES ÉCHANGES (QUESTIONS UTILISATEUR & RÉPONSES IA - DEBUG)`,
        `*Total des échanges audités sans doublon : ${qaList.length}*\n`,
        ...qaList.map((qa) => {
          const sourcesBlock = qa.sources && qa.sources.length > 0
            ? `\n**Passages sources officiels cités :**\n` + qa.sources.map(s => `- [${s.source_type || 'CORPUS_TP2'} | Chunk #${s.chunk_index}] : « ${s.text} »`).join('\n')
            : `\n*Aucune source spécifique requise.*`;
          const traceBlock = qa.agentTrace && qa.agentTrace.length > 0
            ? `\n**Trace d'exécution LangGraph (Statut CHECK : ${qa.verificationStatus}) :**\n` +
              qa.agentTrace.map(st => `- **[${st.step_type}]** (${st.node}) ${st.title} — ${st.detail}`).join('\n')
            : '';
          return `### Échange #${qa.index} [${qa.date}]\n**Question Utilisateur :**\n> ${qa.question}\n\n**Réponse de l'Agent IA :**\n${qa.answer}\n${traceBlock}\n${sourcesBlock}\n`;
        })
      ];
    }

    const memo = [
      `# DOSSIER D'INSTRUCTION & AUDIT — TRIBUNAL JUDICIAIRE DE PARIS`,
      `**Affaire :** ${caseItem.id}`,
      `**Chambre :** ${caseItem.chamber || 'Non précisé'}`,
      `**Date du jugement :** ${caseItem.decision_date || '2025'}`,
      `**Date d'export :** ${new Date().toLocaleDateString('fr-FR')} à ${new Date().toLocaleTimeString('fr-FR')}`,
      `\n---\n`,
      `## I. FAITS DU LITIGE`,
      summary?.faits || 'En attente de génération.',
      `\n## II. PROCÉDURE & PRÉTENTIONS`,
      summary?.procedure || 'En attente de génération.',
      `\n## III. MOTIFS DÉCISIFS & DISPOSITIF`,
      summary?.decision || 'En attente de génération.',
      ...qaSlices,
      `\n---\n*Généré via JurisConsult AI • Tribunal Judiciaire de Paris (2024–2025)*`
    ].join('\n');

    const blob = new Blob([memo], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dossier_${caseItem.id}_audit.md`;
    link.click();
    URL.revokeObjectURL(url);

    setMemoCopied(true);
    setTimeout(() => setMemoCopied(false), 2500);
  };

  // Fonction universelle d'extraction de la substance pure du jugement (supprime les en-têtes d'indexation)
  const extractPureJudgmentText = (rawChunk) => {
    if (!rawChunk) return '';
    let cleaned = rawChunk
      .replace(/^(?:EXTRAIT DU JUGEMENT|EXPOSÉ DU LITIGE|JUGEMENT)[\s\S]*?---\s*\n?/i, '')
      .replace(/^\[JURIDICTION[\s\S]*?---\s*\n?/i, '')
      .replace(/^---.*?\n/m, '')
      .replace(/^[«"'\s]+|[»"'\s]+$/g, '')
      .trim();

    if (cleaned.length < 15 && rawChunk.includes('\n\n')) {
      const parts = rawChunk.split('\n\n');
      cleaned = parts[parts.length - 1].trim();
    }
    return cleaned;
  };

  // Text highlighter universel par empreinte textuelle (tolérant aux espaces et sauts de ligne)
  const renderHighlightedText = () => {
    if (!fullText) return null;
    if (!activeSourceText || activeSourceText.trim().length < 8) {
      return fullText;
    }

    // 1. Isoler le texte pur du jugement (sans cartouche ni faux en-tête)
    const pureText = extractPureJudgmentText(activeSourceText);
    if (!pureText || pureText.length < 8) return fullText;

    // 2. Recherche robuste par regex sur les premiers mots consécutifs (insensible aux sauts de ligne multiples)
    const words = pureText
      .split(/\s+/)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, ''))
      .filter((w) => w.length >= 2)
      .slice(0, 6);

    let idx = -1;
    let matchLength = 0;

    if (words.length >= 2) {
      try {
        const regexPattern = new RegExp(words.join('\\s+'), 'i');
        const m = regexPattern.exec(fullText);
        if (m) {
          idx = m.index;
          matchLength = Math.min(pureText.length, fullText.length - idx);
        }
      } catch (e) {
        // Fallback si la construction regex échoue
      }
    }

    // 3. Fallback recherche directe par sous-chaîne si la regex n'a pas matché
    if (idx === -1) {
      const searchFingerprint = pureText.slice(0, 35).trim();
      idx = fullText.indexOf(searchFingerprint);
      if (idx !== -1) {
        matchLength = Math.min(pureText.length, fullText.length - idx);
      }
    }

    if (idx === -1) {
      return fullText;
    }

    const before = fullText.slice(0, idx);
    const match = fullText.slice(idx, idx + matchLength);
    const after = fullText.slice(idx + matchLength);

    return (
      <>
        {before}
        <mark
          id="active-citation"
          className="bg-amber-200 text-amber-950 px-1 py-0.5 rounded font-medium border-b-2 border-amber-600 shadow-sm transition-all duration-300"
          title="Passage source vérifié"
        >
          {match}
        </mark>
        {after}
      </>
    );
  };

  const legifranceUrl = `https://www.legifrance.gouv.fr/search/all?tab_selection=all&searchField=ALL&query=${encodeURIComponent(caseItem.id || 'tribunal judiciaire paris')}`;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200">
      
      {/* Click outside backdrop detector */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Main Reader Container */}
      <div className="relative z-10 w-full max-w-7xl h-[92vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-paper-300">
        
        {/* Modal Top Header */}
        <header className="px-6 py-4 border-b border-paper-300 bg-paper-50/80 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="uppercase text-[10px] tracking-widest font-mono font-semibold px-2 py-0.5 rounded bg-paper-200 text-ink-700 border border-paper-300">
              Dossier Judiciaire
            </span>
            <div className="flex items-center gap-2 text-xs text-ink-400 font-mono">
              <span>ID: {caseItem.id}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Briefcase className="h-3.5 w-3.5 text-ink-500" />
                <span>{caseItem.chamber || 'Service des référés'}</span>
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-ink-400" />
                <span>{caseItem.decision_date || '2025'}</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href={legifranceUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-950 font-mono transition-colors"
            >
              <span>Légifrance</span>
              <ExternalLink className="h-3 w-3" />
            </a>

            <button
              onClick={onClose}
              className="h-8 w-8 rounded-full bg-paper-100 hover:bg-paper-200 border border-paper-300 flex items-center justify-center text-ink-600 hover:text-ink-950 transition-colors"
              title="Fermer le lecteur (Échap)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Modal Body: Split Screen 60/40 */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
          
          {/* ============================================================== */}
          {/* PANNEAU GAUCHE (7 colonnes = ~58%) : TEXTE INTÉGRAL SURLIGNÉ    */}
          {/* ============================================================== */}
          <div className="lg:col-span-7 flex flex-col border-r border-paper-300 bg-[#FCFCFA] overflow-hidden">
            
            {/* Header du texte */}
            <div className="px-6 py-3 border-b border-paper-200 bg-white flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-ink-700" />
                <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-900">
                  Texte Intégral de la Décision
                </h3>
              </div>

              {activeSourceText ? (
                <div className="flex items-center gap-2 text-xs font-mono text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                  <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                  <span>Passage source surligné</span>
                  <button
                    onClick={() => setActiveSourceText(null)}
                    className="text-[10px] text-amber-900 underline ml-1"
                  >
                    Effacer
                  </button>
                </div>
              ) : (
                <span className="text-[11px] font-mono text-ink-400">
                  Minute certifiée Judilibre
                </span>
              )}
            </div>

            {/* Corps du texte authentique avec scroll et surlignage */}
            <div
              ref={leftTextContainerRef}
              className="flex-1 p-6 sm:p-8 overflow-y-auto text-ink-900 font-serif-legal text-sm leading-relaxed whitespace-pre-wrap selection:bg-paper-300"
            >
              {textLoading ? (
                <div className="flex items-center justify-center h-full text-ink-400 font-mono text-xs">
                  <span className="animate-pulse">Chargement de la minute authentique...</span>
                </div>
              ) : (
                renderHighlightedText()
              )}
            </div>

          </div>

          {/* ============================================================== */}
          {/* PANNEAU DROIT (5 colonnes = ~42%) : SYNTHÈSE + CHATBOT + SAISIE */}
          {/* ============================================================== */}
          <div className="lg:col-span-5 flex flex-col bg-white overflow-hidden">
            
            {/* Right Tabs Header */}
            <div className="px-4 py-2.5 border-b border-paper-200 bg-paper-50 flex items-center justify-between shrink-0">
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setActiveTab('summary')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    activeTab === 'summary'
                      ? 'bg-white text-ink-950 shadow-subtle border border-paper-300 font-semibold'
                      : 'text-ink-500 hover:text-ink-900'
                  }`}
                >
                  Fiche de Synthèse
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('chat')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    activeTab === 'chat'
                      ? 'bg-white text-ink-950 shadow-subtle border border-paper-300 font-semibold'
                      : 'text-ink-500 hover:text-ink-900'
                  }`}
                >
                  Assistant Q&A ({messages.length > 1 ? messages.length - 1 : 0})
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleExportMemo}
                  className="inline-flex items-center gap-1.5 text-[11px] font-mono text-ink-700 hover:text-ink-950 bg-white hover:bg-paper-100 px-2.5 py-1.5 rounded-lg border border-paper-300 transition-all shadow-subtle"
                  title="Exporte la synthèse et l'ensemble des questions/réponses sans doublon en .md"
                >
                  {memoCopied ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-court-emerald" />
                      <span className="text-court-emerald font-semibold">Dossier exporté !</span>
                    </>
                  ) : (
                    <>
                      <Download className="h-3.5 w-3.5 text-ink-500" />
                      <span>Export .md {getDeduplicatedQA(messages).length > 0 ? `(${getDeduplicatedQA(messages).length} Q&A)` : ''}</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Tab 1: Fiche de Synthèse */}
            {activeTab === 'summary' && (
              <div className="flex-1 p-6 overflow-y-auto space-y-5">
                {summaryLoading ? (
                  <div className="flex flex-col items-center justify-center h-full text-center space-y-2 py-12">
                    <RefreshCw className="h-6 w-6 text-ink-400 animate-spin" />
                    <p className="text-xs font-mono text-ink-500">Extraction des Faits, Procédure et Dispositif...</p>
                  </div>
                ) : summaryError ? (
                  <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center space-y-2">
                    <AlertCircle className="h-5 w-5 text-court-crimson mx-auto" />
                    <p className="text-xs text-rose-900">{summaryError}</p>
                    <button
                      onClick={() => loadSummary(true)}
                      className="px-3 py-1 bg-ink-900 text-white text-xs rounded font-medium"
                    >
                      Réessayer
                    </button>
                  </div>
                ) : summary ? (
                  <div className="space-y-5">
                    {/* Faits */}
                    <div className="space-y-1.5">
                      <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-court-crimson">
                        I. Faits constants
                      </h4>
                      <p className="text-xs sm:text-sm text-ink-800 leading-relaxed font-serif-legal">
                        {summary.faits || 'Non explicité.'}
                      </p>
                    </div>

                    {/* Procédure */}
                    <div className="space-y-1.5 border-t border-paper-200 pt-4">
                      <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-court-crimson">
                        II. Procédure & Prétentions
                      </h4>
                      <p className="text-xs sm:text-sm text-ink-800 leading-relaxed font-serif-legal">
                        {summary.procedure || 'Non explicité.'}
                      </p>
                    </div>

                    {/* Décision */}
                    <div className="space-y-1.5 border-t border-paper-200 pt-4">
                      <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-court-crimson">
                        III. Motifs décisifs & Dispositif
                      </h4>
                      <div className="pl-3.5 py-1 border-l-2 border-ink-900 bg-paper-50/80 rounded-r">
                        <p className="text-xs sm:text-sm text-ink-950 font-serif-legal font-medium leading-relaxed">
                          {summary.decision || 'Non explicité.'}
                        </p>
                      </div>
                    </div>

                    {/* IV. Historique des questions & réponses dédupliquées pour debug */}
                    <div className="space-y-3 border-t border-paper-200 pt-5">
                      <div className="flex items-center justify-between">
                        <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-court-crimson flex items-center gap-1.5">
                          <MessageSquare className="h-3.5 w-3.5" />
                          <span>IV. Questions posées & Réponses IA ({getDeduplicatedQA(messages).length})</span>
                        </h4>
                        {getDeduplicatedQA(messages).length > 0 && (
                          <span className="text-[10px] font-mono text-court-emerald bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                            Dédupliqué pour l'export
                          </span>
                        )}
                      </div>

                      {getDeduplicatedQA(messages).length === 0 ? (
                        <div className="p-3.5 rounded-xl bg-paper-50 border border-paper-300 text-xs text-ink-500 font-mono leading-relaxed">
                          Aucune question posée pour l'instant. Utilisez la barre de saisie ci-dessous : chaque question et sa réponse sourcée s'ajouteront ici automatiquement sans doublon et seront intégrées au fichier .md lors de l'export.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {getDeduplicatedQA(messages).map((qa) => (
                            <div key={qa.id} className="p-3.5 rounded-xl bg-paper-50/80 border border-paper-300 text-xs space-y-2">
                              <div className="flex items-center justify-between text-[11px] font-mono text-ink-500">
                                <span className="font-semibold text-ink-900 bg-paper-200 px-1.5 py-0.5 rounded">
                                  Échange #{qa.index}
                                </span>
                                <span>{qa.date}</span>
                              </div>
                              <p className="font-medium text-ink-900 italic">
                                « {qa.question} »
                              </p>
                              <div className="pt-2 border-t border-paper-200 text-ink-850 font-serif-legal leading-relaxed whitespace-pre-wrap">
                                {qa.answer}
                              </div>
                              {qa.agentTrace && qa.agentTrace.length > 0 && (
                                <AgentTracePanel
                                  trace={qa.agentTrace}
                                  metrics={qa.metrics}
                                  verificationStatus={qa.verificationStatus}
                                />
                              )}
                              {qa.sources && qa.sources.length > 0 && (
                                <div className="pt-1.5 flex flex-wrap gap-1.5 items-center">
                                  <span className="text-[10px] font-mono text-ink-400">Sources citées :</span>
                                  {qa.sources.map((s, sIdx) => {
                                    const isExternal = s.source_type === 'SOURCE_EXTERNE';
                                    return (
                                      <button
                                        key={sIdx}
                                        type="button"
                                        onClick={() => !isExternal && setActiveSourceText(s.text)}
                                        className={`inline-flex items-center gap-1 font-mono text-[10px] px-2 py-0.5 rounded border transition-colors shadow-subtle ${
                                          isExternal
                                            ? 'bg-indigo-50 text-indigo-900 border-indigo-200 cursor-default'
                                            : 'bg-white hover:bg-amber-100 hover:text-amber-950 text-ink-700 border-paper-300'
                                        }`}
                                        title={isExternal ? s.text : 'Cliquer pour surligner dans le texte officiel à gauche'}
                                      >
                                        <Quote className="h-2.5 w-2.5 text-court-crimson" />
                                        <span>
                                          {isExternal
                                            ? `[SOURCE_EXTERNE] ${s.title || `Réf. #${s.chunk_index}`}`
                                            : `[CORPUS_TP2] Chunk #${s.chunk_index}`}
                                        </span>
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                  </div>
                ) : null}
              </div>
            )}

            {/* Tab 2: Conversation Chatbot Stream */}
            {activeTab === 'chat' && (
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {messages.map((m, mIdx) => (
                  <div
                    key={mIdx}
                    className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'} space-y-1`}
                  >
                    <span className="text-[10px] font-mono text-ink-400 px-1">
                      {m.role === 'user' ? 'Vous' : 'JurisConsult Assistant'}
                    </span>

                    <div className={`max-w-[90%] p-3.5 rounded-xl text-xs sm:text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-ink-900 text-paper-50 rounded-tr-none shadow-subtle'
                        : 'bg-paper-50 border border-paper-300 text-ink-900 rounded-tl-none font-serif-legal shadow-subtle'
                    }`}>
                      <p className="whitespace-pre-wrap">{m.content}</p>

                      {/* Trace d'exécution Agentic RAG (LangGraph) */}
                      {m.agentTrace && m.agentTrace.length > 0 && (
                        <AgentTracePanel
                          trace={m.agentTrace}
                          metrics={m.metrics}
                          verificationStatus={m.verificationStatus}
                        />
                      )}

                      {/* Source Citation Pills ([CORPUS_TP2] vs [SOURCE_EXTERNE]) */}
                      {m.sources && m.sources.length > 0 && (
                        <div className="mt-3 pt-2.5 border-t border-paper-200 space-y-1.5">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block font-semibold">
                            Citations & Passages sources ([CORPUS_TP2] / [SOURCE_EXTERNE]) :
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {m.sources.map((s, sIdx) => {
                              const isExternal = s.source_type === 'SOURCE_EXTERNE';
                              return (
                                <button
                                  key={sIdx}
                                  type="button"
                                  onClick={() => !isExternal && setActiveSourceText(s.text)}
                                  className={`inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded border transition-colors shadow-subtle ${
                                    isExternal
                                      ? 'bg-indigo-50 text-indigo-900 border-indigo-200 cursor-default'
                                      : 'bg-white hover:bg-amber-100 hover:text-amber-950 border-paper-300 hover:border-amber-400 text-ink-700'
                                  }`}
                                  title={isExternal ? s.text : 'Cliquer pour surligner et scroller vers ce passage à gauche'}
                                >
                                  <Quote className="h-3 w-3 text-court-crimson" />
                                  <span>
                                    {isExternal
                                      ? `[SOURCE_EXTERNE] ${s.title || `Réf. #${s.chunk_index}`}`
                                      : `[CORPUS_TP2] Source #${sIdx + 1} (Chunk #${s.chunk_index})`}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {chatLoading && (
                  <div className="flex items-center gap-2 text-xs text-ink-400 font-mono py-2">
                    <span className="h-2 w-2 rounded-full bg-court-brass animate-ping" />
                    <span>Recherche des attendus et rédaction de la réponse...</span>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}

            {/* Sticky Chat Input Bar (Available everywhere in the dossier) */}
            <form
              onSubmit={handleSendChat}
              className="p-3 border-t border-paper-300 bg-white flex items-center gap-2 shrink-0"
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Posez une question sur cette affaire (ex: Y a-t-il une condamnation à l'article 700 ?)..."
                className="flex-1 px-4 py-2.5 bg-paper-50 border border-paper-300 rounded-xl text-ink-950 placeholder-ink-400 focus:outline-none focus:bg-white focus:border-ink-900 focus:ring-1 focus:ring-ink-900 text-xs sm:text-sm transition-all"
              />
              <button
                type="submit"
                disabled={chatLoading || !chatInput.trim()}
                className="p-2.5 bg-ink-900 hover:bg-ink-800 disabled:opacity-40 text-paper-50 rounded-xl transition-all shadow-subtle shrink-0"
                title="Poser la question"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>

          </div>

        </div>

      </div>

    </div>
  );
}
