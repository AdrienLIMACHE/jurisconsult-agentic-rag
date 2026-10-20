import React from 'react';
import { Calendar, Briefcase, ChevronRight, FileText, Scale } from 'lucide-react';

export default function CaseList({ results, selectedCase, onSelectCase, query }) {
  if (!results || results.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-paper-300 p-8 text-center text-ink-400 shadow-subtle">
        <Scale className="h-8 w-8 text-paper-400 mx-auto mb-2" />
        <p className="text-xs font-semibold text-ink-800">Aucune décision trouvée</p>
        <p className="text-[11px] text-ink-400 mt-1">
          Ajustez votre requête ou cliquez sur une des thématiques ci-dessus.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      
      {/* Header List Summary */}
      <div className="flex items-center justify-between text-xs px-1 text-ink-500">
        <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-ink-600 font-semibold">
          <span>Rôle & Décisions Référencées</span>
          <span className="px-1.5 py-0.2 rounded bg-paper-200 text-ink-800 text-[10px]">
            {results.length}
          </span>
        </div>
        
        {query && (
          <span className="text-[11px] text-ink-400 truncate max-w-[240px]">
            Pour « <em className="text-ink-700 not-italic font-medium">{query}</em> »
          </span>
        )}
      </div>

      {/* Cards List */}
      <div className="space-y-2">
        {results.map((c, idx) => {
          const isSelected = selectedCase?.id === c.id;
          const matchPercent = Math.max(75, 98 - idx * 4);

          return (
            <div
              key={c.id}
              onClick={() => onSelectCase(c)}
              className={`group p-4 rounded-lg border transition-all cursor-pointer text-left relative ${
                isSelected
                  ? 'bg-white border-ink-900 shadow-subtle ring-1 ring-ink-900/15'
                  : 'bg-white border-paper-300 hover:border-paper-500 hover:bg-paper-50/50'
              }`}
            >
              {/* Left active marker indicator */}
              {isSelected && (
                <div className="absolute left-0 top-3 bottom-3 w-1 bg-ink-900 rounded-r" />
              )}

              {/* Court header & Relevance score */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="uppercase text-[9px] tracking-widest font-mono text-ink-400 font-semibold block mb-0.5">
                    {c.location || 'Tribunal Judiciaire de Paris'}
                  </span>
                  <h4 className="text-xs sm:text-sm font-semibold text-ink-900 leading-snug line-clamp-1 group-hover:text-ink-950">
                    {c.solution || 'Ordonnance du Tribunal judiciaire de Paris'}
                  </h4>
                </div>

                {/* Match score badge (Understated & Monospace) */}
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border shrink-0 ${
                  isSelected
                    ? 'bg-ink-900 text-paper-50 border-ink-900 font-medium'
                    : 'bg-paper-100 text-ink-600 border-paper-300'
                }`}>
                  {matchPercent}% score
                </span>
              </div>

              {/* Chamber & Date metadata strip */}
              <div className="flex items-center gap-3 text-[11px] text-ink-400 mt-2 font-mono">
                <span className="flex items-center gap-1 truncate">
                  <Briefcase className="h-3 w-3 text-ink-400 shrink-0" />
                  <span>{c.chamber || 'Service des référés'}</span>
                </span>
                <span className="text-paper-400">•</span>
                <span className="flex items-center gap-1 shrink-0">
                  <Calendar className="h-3 w-3 text-ink-400" />
                  <span>{c.decision_date || '2025'}</span>
                </span>
              </div>

              {/* Excerpt snippet */}
              <p className="text-xs text-ink-600 mt-2 line-clamp-2 leading-relaxed font-sans">
                {c.snippet}
              </p>

              {/* Footer row with ID & Selection cue */}
              <div className="mt-2.5 pt-2 border-t border-paper-200 flex items-center justify-between text-[10px] font-mono text-ink-400">
                <span>ID : {c.id.slice(0, 14)}...</span>
                <span className={`flex items-center gap-0.5 transition-colors ${
                  isSelected ? 'text-ink-900 font-medium' : 'text-ink-400 group-hover:text-ink-700'
                }`}>
                  {isSelected ? 'Dossier ouvert' : 'Ouvrir le dossier'}
                  <ChevronRight className="h-3 w-3" />
                </span>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
