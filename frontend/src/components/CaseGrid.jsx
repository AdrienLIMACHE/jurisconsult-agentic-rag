import React, { useState, useEffect, useRef } from 'react';
import { Calendar, Briefcase, ArrowUpRight, Scale, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

const ITEMS_PER_PAGE = 10;

export default function CaseGrid({ cases, onSelectCase, isSearch, query, onResetSearch }) {
  const [currentPage, setCurrentPage] = useState(1);
  const gridTopRef = useRef(null);

  // Réinitialiser à la page 1 si la liste ou la requête change
  useEffect(() => {
    setCurrentPage(1);
  }, [cases, query]);

  if (!cases || cases.length === 0) {
    return (
      <div className="max-w-4xl mx-auto my-12 p-12 text-center bg-white rounded-2xl border border-paper-300 shadow-subtle">
        <Scale className="h-10 w-10 text-paper-400 mx-auto mb-3" />
        <h3 className="text-base font-semibold text-ink-900">Aucune décision trouvée</h3>
        <p className="text-xs text-ink-400 mt-1 max-w-sm mx-auto">
          Modifiez vos termes de recherche ou relancez la découverte aléatoire.
        </p>
        {isSearch && (
          <button
            type="button"
            onClick={onResetSearch}
            className="mt-4 px-4 py-2 rounded-xl bg-ink-900 text-white text-xs font-medium hover:bg-ink-800 transition-colors"
          >
            Revenir aux affaires aléatoires
          </button>
        )}
      </div>
    );
  }

  // Tri explicite du plus pertinent au moins pertinent si recherche
  const sortedCases = isSearch
    ? [...cases].sort((a, b) => (b.score || 0) - (a.score || 0))
    : cases;

  // Calculs de pagination (10 par page)
  const totalItems = sortedCases.length;
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const paginatedCases = sortedCases.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  const handlePageChange = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
    gridTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <section ref={gridTopRef} className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-paper-200">
        <div className="flex items-center gap-2.5">
          <span className="h-2 w-2 rounded-full bg-court-emerald" />
          <h2 className="text-sm font-semibold text-ink-900">
            {isSearch ? `Résultats de recherche pour « ${query} »` : "Sélection d'affaires du Tribunal de Paris"}
          </h2>
          <span className="text-xs font-mono text-ink-400">
            ({totalItems} décisions trouvées • triées par pertinence)
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isSearch ? (
            <button
              type="button"
              onClick={onResetSearch}
              className="text-xs text-ink-600 hover:text-ink-950 font-mono underline hover:no-underline transition-all"
            >
              ← Revenir à la sélection aléatoire
            </button>
          ) : (
            <span className="text-xs text-ink-400 hidden sm:inline">
              10 décisions par page • Cliquez pour ouvrir le dossier
            </span>
          )}
        </div>
      </div>

      {/* Grid de 10 cartes par page (2 ou 3 colonnes) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-2 gap-5">
        {paginatedCases.map((item, idx) => {
          const scorePercent = item.score !== undefined ? Math.round(item.score * 100) : null;
          const globalRank = startIndex + idx + 1;

          return (
            <div
              key={item.id || idx}
              onClick={() => onSelectCase(item)}
              className="group relative flex flex-col justify-between p-6 rounded-2xl bg-white border border-paper-300 hover:border-ink-900 shadow-subtle hover:shadow-elevated hover:-translate-y-0.5 transition-all duration-200 cursor-pointer text-left"
            >
              {/* Top metadata strip & Score de pertinence */}
              <div className="space-y-3">
                <div className="flex items-center justify-between text-[11px] font-mono text-ink-400">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ink-700 bg-paper-100 px-2 py-0.5 rounded text-[10px] border border-paper-300">
                      #{globalRank}
                    </span>
                    <span className="flex items-center gap-1.5 truncate max-w-[220px]">
                      <Briefcase className="h-3.5 w-3.5 text-ink-500 shrink-0" />
                      <span className="truncate">{item.chamber || 'Service des référés'}</span>
                    </span>
                  </div>

                  {/* Affichage du score de pertinence décroissant */}
                  {isSearch && scorePercent !== null ? (
                    <span className={`inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold px-2.5 py-0.5 rounded-full border shadow-subtle ${
                      scorePercent >= 90
                        ? 'bg-emerald-50 text-court-emerald border-emerald-200'
                        : scorePercent >= 75
                        ? 'bg-paper-100 text-ink-800 border-paper-300'
                        : 'bg-paper-50 text-ink-600 border-paper-200'
                    }`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${scorePercent >= 90 ? 'bg-court-emerald' : 'bg-court-brass'}`} />
                      <span>{scorePercent}% match</span>
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5 text-ink-400" />
                      <span>{item.decision_date || '2025'}</span>
                    </span>
                  )}
                </div>

                {/* Solution Title */}
                <div>
                  <h3 className="font-serif text-base font-semibold text-ink-950 leading-snug line-clamp-2 group-hover:text-ink-900 transition-colors">
                    {item.solution || 'Décision du Tribunal judiciaire de Paris'}
                  </h3>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-ink-400 mt-1">
                    <span>{item.location || 'Tribunal Judiciaire de Paris'}</span>
                    <span>•</span>
                    <span>{item.decision_date || '2025'}</span>
                  </div>
                </div>

                {/* Snippet preview */}
                <p className="text-xs text-ink-600 leading-relaxed line-clamp-3 font-sans">
                  {item.snippet || "Ordonnance rendue dans le ressort de la juridiction parisienne."}
                </p>
              </div>

              {/* Bottom action bar */}
              <div className="mt-5 pt-3.5 border-t border-paper-200 flex items-center justify-between text-xs font-medium text-ink-500 group-hover:text-ink-950 transition-colors">
                <span className="font-mono text-[11px] text-ink-400">ID: {item.id?.slice(0, 14)}...</span>
                <span className="inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform text-ink-800 font-semibold">
                  <span>Consulter le dossier</span>
                  <ArrowUpRight className="h-4 w-4" />
                </span>
              </div>

            </div>
          );
        })}
      </div>

      {/* Pagination Bar (10 par page) */}
      {totalPages > 1 && (
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-paper-200 text-xs font-mono text-ink-500">
          <div>
            Affichage des décisions <strong>{startIndex + 1}</strong> à <strong>{Math.min(startIndex + ITEMS_PER_PAGE, totalItems)}</strong> sur <strong>{totalItems}</strong>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-paper-300 bg-white hover:bg-paper-100 disabled:opacity-30 disabled:pointer-events-none transition-all"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Précédent</span>
            </button>

            {/* Page number buttons */}
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                <button
                  key={pageNum}
                  type="button"
                  onClick={() => handlePageChange(pageNum)}
                  className={`h-8 w-8 rounded-lg flex items-center justify-center transition-all ${
                    currentPage === pageNum
                      ? 'bg-ink-900 text-white font-semibold shadow-subtle'
                      : 'bg-white hover:bg-paper-100 border border-paper-300 text-ink-700'
                  }`}
                >
                  {pageNum}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-paper-300 bg-white hover:bg-paper-100 disabled:opacity-30 disabled:pointer-events-none transition-all"
            >
              <span>Suivant</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

    </section>
  );
}
