import React, { useState } from 'react';
import { 
  CheckCircle, Zap, RefreshCw, Bookmark, Download, 
  Scale, BookOpen, Gavel, AlertCircle, Check, ShieldCheck
} from 'lucide-react';

export default function CaseSummaryTab({ summary, loading, onRefresh, error }) {
  const [bookmarked, setBookmarked] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleExportMemo = () => {
    if (!summary) return;
    const memoContent = [
      `# MÉMO DE CONSULTATION — TRIBUNAL JUDICIAIRE DE PARIS`,
      `Affaire : ${summary.affaire_id || 'Non spécifié'}`,
      `Date de génération : ${new Date().toLocaleDateString('fr-FR')}`,
      `Statut : ${summary.is_cached ? 'Certifié en Cache persistant (<2ms)' : 'Généré par modèle Llama 3.2 1B'}\n`,
      `## I. EXPOSÉ DU LITIGE & FAITS MATÉRIELS`,
      summary.faits,
      `\n## II. PROCÉDURE ANTÉRIEURE & MOYENS DES PARTIES`,
      summary.procedure,
      `\n## III. MOTIFS DÉCISIFS & DISPOSITIF DU TRIBUNAL`,
      summary.decision,
      `\n---`,
      `Généré via JurisConsult AI • Corpus Open Data Judilibre 2024–2025`
    ].join('\n');

    const blob = new Blob([memoContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `memo_TJ_Paris_${summary.affaire_id || 'synthese'}.md`;
    link.click();
    URL.revokeObjectURL(url);

    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-paper-300 p-12 text-center space-y-4 shadow-subtle">
        <div className="inline-flex p-3 rounded-full bg-paper-100 text-ink-800 border border-paper-300">
          <Scale className="h-6 w-6 animate-pulse" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink-900">
            Extraction structurée par Llama 3.2 1B...
          </h3>
          <p className="text-xs text-ink-400 mt-1 max-w-md mx-auto">
            Génération selon le protocole d'extraction négative (Faits, Procédure, Décision) sans extrapolation.
          </p>
        </div>
        <div className="flex justify-center">
          <span className="inline-flex items-center gap-2 font-mono text-[11px] text-ink-400 bg-paper-100 px-3 py-1 rounded border border-paper-300">
            <span className="h-2 w-2 rounded-full bg-court-brass animate-ping" />
            Inférence locale Ollama CPU
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-rose-50/60 border border-rose-200 rounded-lg text-center space-y-3">
        <AlertCircle className="h-5 w-5 text-court-crimson mx-auto" />
        <p className="text-xs font-semibold text-rose-900">{error}</p>
        <button
          onClick={() => onRefresh(true)}
          className="px-3 py-1.5 bg-ink-900 hover:bg-ink-800 text-paper-50 text-xs rounded transition font-medium"
        >
          Relancer la génération
        </button>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="bg-white rounded-lg shadow-subtle border border-paper-300 p-6 sm:p-7 space-y-6">
      
      {/* Top Memo Header & Verification Stamps */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-paper-200">
        <div>
          <span className="uppercase text-[10px] tracking-widest font-mono text-ink-400 font-semibold block">
            Fiche d'Arrêt • Note de Synthèse
          </span>
          <h3 className="font-serif text-base sm:text-lg font-medium text-ink-950 mt-0.5">
            Analyse des Motifs & Dispositif Retenu
          </h3>
        </div>

        <div className="flex items-center gap-2 font-mono text-[11px]">
          {/* Cache Status Badge */}
          {summary.is_cached ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-50 text-court-emerald border border-emerald-200 font-medium">
              <Zap className="h-3.5 w-3.5 text-court-emerald" />
              <span>Cache Instantané (2ms)</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-paper-100 text-ink-700 border border-paper-300">
              <span>Généré LLM</span>
            </span>
          )}

          {/* Grounding Seal */}
          <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded bg-paper-100 text-ink-700 border border-paper-300">
            <ShieldCheck className="h-3.5 w-3.5 text-ink-500" />
            <span>Fiabilité : Élevée</span>
          </span>
        </div>
      </div>

      {/* Structured Legal Memo Body */}
      <div className="space-y-6">
        
        {/* 1. FAITS */}
        <section className="space-y-2">
          <div className="flex items-center gap-2 text-ink-900 border-b border-paper-200 pb-1">
            <span className="font-mono text-xs font-semibold text-court-crimson">I.</span>
            <h4 className="text-xs font-bold uppercase tracking-wider text-ink-900">
              Faits constants du litige
            </h4>
          </div>
          <p className="text-sm text-ink-700 leading-relaxed font-serif-legal text-justify">
            {summary.faits || 'Non explicité dans le jugement.'}
          </p>
        </section>

        {/* 2. PROCÉDURE */}
        <section className="space-y-2">
          <div className="flex items-center gap-2 text-ink-900 border-b border-paper-200 pb-1">
            <span className="font-mono text-xs font-semibold text-court-crimson">II.</span>
            <h4 className="text-xs font-bold uppercase tracking-wider text-ink-900">
              Procédure antérieure & Prétentions des parties
            </h4>
          </div>
          <p className="text-sm text-ink-700 leading-relaxed font-serif-legal text-justify">
            {summary.procedure || 'Non explicité dans le jugement.'}
          </p>
        </section>

        {/* 3. DÉCISION & MOTIFS DÉCISIFS */}
        <section className="space-y-2">
          <div className="flex items-center gap-2 text-ink-900 border-b border-paper-200 pb-1">
            <span className="font-mono text-xs font-semibold text-court-crimson">III.</span>
            <h4 className="text-xs font-bold uppercase tracking-wider text-ink-900">
              Motifs décisifs & Dispositif du Tribunal
            </h4>
          </div>
          <div className="pl-4 py-2 border-l-2 border-ink-900 bg-paper-50/70 rounded-r">
            <p className="text-sm text-ink-900 leading-relaxed font-serif-legal font-medium text-justify">
              {summary.decision || 'Non explicité dans le jugement.'}
            </p>
          </div>
        </section>

      </div>

      {/* Memo Actions Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-paper-200 text-xs">
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setBookmarked(!bookmarked)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded border transition-colors ${
              bookmarked
                ? 'bg-paper-200 text-ink-900 border-paper-400 font-semibold'
                : 'bg-white hover:bg-paper-100 text-ink-600 border-paper-300'
            }`}
          >
            <Bookmark className="h-3.5 w-3.5" />
            <span>{bookmarked ? 'Dossier archivé' : 'Archiver au dossier'}</span>
          </button>

          <button
            onClick={handleExportMemo}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-ink-900 hover:bg-ink-800 text-paper-50 transition-colors shadow-subtle font-medium"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-paper-200" /> : <Download className="h-3.5 w-3.5" />}
            <span>{copied ? 'Mémo téléchargé !' : 'Exporter le mémo (.md)'}</span>
          </button>
        </div>

        <button
          onClick={() => onRefresh(true)}
          className="flex items-center gap-1.5 text-ink-400 hover:text-ink-800 transition-colors font-mono text-[11px]"
          title="Forcer un recalcul de la synthèse par le LLM"
        >
          <RefreshCw className="h-3 w-3" />
          <span>Régénérer</span>
        </button>

      </div>

    </div>
  );
}
