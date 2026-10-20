import React, { useState, useEffect } from 'react';
import { Calendar, Briefcase, FileText, MessageSquare, BookOpen, ExternalLink, Copy, Check } from 'lucide-react';
import CaseSummaryTab from './CaseSummaryTab';
import CaseChatTab from './CaseChatTab';
import CaseFullTextTab from './CaseFullTextTab';
import { getSummary, getCaseDetail } from '../services/api';

export default function CaseDetail({ affaire, onSummaryLoaded, onSelectChunk }) {
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'chat' | 'text'
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);
  const [fullText, setFullText] = useState(affaire?.text || '');
  const [copiedId, setCopiedId] = useState(false);

  useEffect(() => {
    if (!affaire?.id) return;
    loadSummary(false);
    loadFullText();
  }, [affaire?.id]);

  const loadSummary = async (forceRefresh = false) => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await getSummary(affaire.id, forceRefresh);
      setSummary(data);
      if (onSummaryLoaded) onSummaryLoaded();
    } catch (err) {
      setSummaryError(err.message || 'Erreur lors de la génération du résumé.');
    } finally {
      setSummaryLoading(false);
    }
  };

  const loadFullText = async () => {
    if (affaire.text) {
      setFullText(affaire.text);
      return;
    }
    try {
      const data = await getCaseDetail(affaire.id);
      setFullText(data.text || '');
    } catch (err) {
      setFullText('Texte intégral non disponible.');
    }
  };

  const handleCopyId = () => {
    navigator.clipboard.writeText(affaire.id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const legifranceUrl = `https://www.legifrance.gouv.fr/search/all?tab_selection=all&searchField=ALL&query=${encodeURIComponent(affaire.id || 'tribunal judiciaire paris')}`;

  return (
    <div className="space-y-4">
      
      {/* Dossier Header Card */}
      <div className="bg-white rounded-lg border border-paper-300 shadow-subtle p-5 sm:p-6 space-y-4">
        
        {/* Official Header Strip */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-paper-200">
          <div className="flex items-center gap-2">
            <span className="uppercase text-[10px] tracking-widest font-mono text-ink-500 font-semibold">
              Dossier Judiciaire
            </span>
            <span className="text-paper-400">•</span>
            <button
              onClick={handleCopyId}
              className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-600 bg-paper-100 hover:bg-paper-200 border border-paper-300 px-2 py-0.5 rounded transition-colors"
              title="Copier l'identifiant Légifrance / Judilibre"
            >
              <span>ID: {affaire.id}</span>
              {copiedId ? <Check className="h-3 w-3 text-court-emerald" /> : <Copy className="h-3 w-3 text-ink-400" />}
            </button>
          </div>

          <div className="flex items-center gap-3 text-xs text-ink-400 font-mono">
            <span className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5 text-ink-400" />
              <span>{affaire.decision_date || '2025'}</span>
            </span>
            <span>•</span>
            <a
              href={legifranceUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-ink-500 hover:text-ink-900 transition-colors"
            >
              <span>Légifrance</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>

        {/* Case Solution Title in Editorial Serif */}
        <div>
          <span className="text-[11px] font-mono text-court-crimson uppercase tracking-wider font-semibold">
            {affaire.chamber || 'Service des référés du Tribunal judiciaire de Paris'}
          </span>
          <h2 className="text-lg sm:text-xl font-serif font-medium text-ink-950 leading-snug mt-1">
            {affaire.solution || 'Décision rendue par le Tribunal judiciaire de Paris'}
          </h2>
          <p className="text-xs text-ink-400 mt-1">
            Arrêt certifié Open Data Judilibre • Ressort de la Cour d'appel de Paris
          </p>
        </div>

        {/* Editorial Navigation Tabs */}
        <div className="flex gap-1 pt-2 border-t border-paper-200 overflow-x-auto no-scrollbar font-mono text-xs">
          <button
            onClick={() => setActiveTab('summary')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded transition-all font-medium ${
              activeTab === 'summary'
                ? 'bg-ink-900 text-paper-50 shadow-subtle'
                : 'text-ink-500 hover:text-ink-900 hover:bg-paper-100'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Fiche de Synthèse</span>
          </button>

          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded transition-all font-medium ${
              activeTab === 'chat'
                ? 'bg-ink-900 text-paper-50 shadow-subtle'
                : 'text-ink-500 hover:text-ink-900 hover:bg-paper-100'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            <span>Interrogateur Q&A</span>
          </button>

          <button
            onClick={() => setActiveTab('text')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded transition-all font-medium ${
              activeTab === 'text'
                ? 'bg-ink-900 text-paper-50 shadow-subtle'
                : 'text-ink-500 hover:text-ink-900 hover:bg-paper-100'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Texte Intégral du Greffe</span>
          </button>
        </div>

      </div>

      {/* Tab Panels */}
      <div>
        {activeTab === 'summary' && (
          <CaseSummaryTab
            summary={summary}
            loading={summaryLoading}
            error={summaryError}
            onRefresh={(force) => loadSummary(force)}
          />
        )}

        {activeTab === 'chat' && (
          <CaseChatTab
            affaireId={affaire.id}
            onSelectChunk={onSelectChunk}
          />
        )}

        {activeTab === 'text' && (
          <CaseFullTextTab text={fullText} />
        )}
      </div>

    </div>
  );
}
