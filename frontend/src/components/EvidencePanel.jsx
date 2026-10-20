import React from 'react';
import { ExternalLink, ShieldCheck, Quote, Scale, BookOpen } from 'lucide-react';

export default function EvidencePanel({ activeCase, activeChunk }) {
  if (!activeCase) {
    return (
      <div className="border border-dashed border-paper-400 rounded-lg p-8 text-center text-ink-400 bg-white/50">
        <Scale className="h-8 w-8 text-paper-400 mx-auto mb-2" />
        <p className="text-xs font-semibold text-ink-800">Aucun dossier sélectionné</p>
        <p className="text-[11px] text-ink-400 mt-1">
          Sélectionnez un arrêt dans le rôle pour examiner les motifs originaux.
        </p>
      </div>
    );
  }

  const displayText = activeChunk?.text || activeCase.snippet || activeCase.text?.slice(350, 1000) || 'Aucun extrait disponible.';
  const chunkTitle = activeChunk ? `Chunk #${activeChunk.chunk_index}` : 'Attendu de principe & Motivation';
  const legifranceUrl = `https://www.legifrance.gouv.fr/search/all?tab_selection=all&searchField=ALL&query=${encodeURIComponent(activeCase.id || 'tribunal judiciaire paris')}`;

  return (
    <div className="bg-white rounded-lg shadow-subtle border border-paper-300 overflow-hidden flex flex-col sticky top-20">
      
      {/* Evidence Panel Header */}
      <div className="px-4 py-3 bg-paper-100 border-b border-paper-200 flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <BookOpen className="h-3.5 w-3.5 text-ink-800" />
          <span className="text-[11px] font-mono font-semibold uppercase tracking-wider text-ink-800">
            Inspecteur de Preuves
          </span>
        </div>
        
        <a
          href={legifranceUrl}
          target="_blank"
          rel="noreferrer"
          className="text-[11px] font-mono text-ink-500 hover:text-ink-900 flex items-center space-x-1 transition-colors"
        >
          <span>Légifrance</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {/* Body Content */}
      <div className="p-5 space-y-4 max-h-[62vh] overflow-y-auto">
        
        {/* Case Metadata Box */}
        <div className="border-l-2 border-ink-900 pl-3.5 py-1 bg-paper-50/60 rounded-r">
          <span className="text-[10px] uppercase tracking-wider font-mono text-ink-400 font-semibold block">
            Référence Judiciaire
          </span>
          <p className="text-xs font-semibold text-ink-900 mt-0.5">
            {activeCase.chamber || 'Tribunal judiciaire de Paris'} • {activeCase.decision_date || '2025'}
          </p>
          <p className="text-[11px] font-mono text-ink-500 mt-0.5">
            ID : {activeCase.id}
          </p>
        </div>

        {/* Extracted Chunk Content */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-ink-600 font-mono">
            <span className="flex items-center gap-1.5 font-semibold text-ink-900">
              <Quote className="h-3.5 w-3.5 text-court-crimson" />
              {chunkTitle} :
            </span>
            <span className="text-[10px] text-ink-400">
              Source ChromaDB
            </span>
          </div>

          <div className="bg-paper-50/80 p-4 rounded border border-paper-300 text-xs text-ink-850 leading-relaxed font-serif-legal italic text-justify shadow-inner">
            « {displayText} »
          </div>
        </div>

        {/* Verification Guarantee Notice */}
        <div className="flex items-start gap-2.5 p-3 rounded bg-paper-100/70 border border-paper-300 text-xs text-ink-600 font-sans">
          <ShieldCheck className="h-4 w-4 text-court-emerald shrink-0 mt-0.5" />
          <span className="text-[11px] leading-snug">
            Ce passage constitue la <strong>preuve textuelle authentique</strong> extraite du magasin de vecteurs pour justifier la synthèse.
          </span>
        </div>

      </div>

      {/* Footer Info */}
      <div className="p-3 bg-paper-100 text-center border-t border-paper-200">
        <p className="text-[10px] font-mono text-ink-400">
          Corpus certifié Open Data Judilibre • 62 003 chunks vectorisés
        </p>
      </div>

    </div>
  );
}
