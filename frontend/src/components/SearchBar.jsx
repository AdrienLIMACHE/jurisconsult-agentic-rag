import React, { useState } from 'react';
import { Search, CornerDownLeft, Sparkles } from 'lucide-react';

export default function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSearch(query.trim());
  };

  return (
    <section className="w-full max-w-4xl mx-auto text-center pt-8 pb-4 px-4 space-y-6">
      
      {/* Hero Badge */}
      <div className="inline-flex items-center gap-2 rounded-full border border-paper-300 bg-white px-3.5 py-1 text-xs font-medium text-ink-600 shadow-subtle">
        <Sparkles className="h-3.5 w-3.5 text-court-brass" />
        <span>Corpus officiel 2024–2025 • Tribunal judiciaire de Paris</span>
      </div>

      {/* Hero Title */}
      <div className="space-y-2">
        <h1 className="text-3xl sm:text-5xl font-serif font-semibold tracking-tight text-ink-950 leading-tight">
          Explorez la jurisprudence en toute clarté.
        </h1>
        <p className="text-sm sm:text-base text-ink-500 max-w-2xl mx-auto font-light leading-relaxed">
          Posez une question juridique ou décrivez les faits d'un litige. Le moteur hybride identifie les décisions pertinentes et synthétise les motifs.
        </p>
      </div>

      {/* Main Single Search Input */}
      <form onSubmit={handleSubmit} className="relative max-w-3xl mx-auto pt-2">
        <div className="relative flex items-center shadow-elevated rounded-2xl bg-white border border-paper-300 focus-within:border-ink-900 focus-within:ring-2 focus-within:ring-ink-900/10 transition-all">
          <div className="absolute left-4.5 text-ink-400 pointer-events-none">
            <Search className="h-5 w-5" />
          </div>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ex: Expulsion locative clause résolutoire, amende meublé de tourisme..."
            className="w-full pl-12 pr-32 py-4 rounded-2xl bg-transparent text-ink-950 placeholder-ink-400 focus:outline-none text-sm sm:text-base"
          />

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-2 top-2 bottom-2 px-5 bg-ink-900 hover:bg-ink-800 disabled:opacity-40 text-paper-50 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-2 transition-all shadow-subtle"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 border-2 border-paper-200/40 border-t-white rounded-full animate-spin" />
                <span>Recherche...</span>
              </span>
            ) : (
              <>
                <span>Rechercher</span>
                <CornerDownLeft className="h-3.5 w-3.5 text-paper-400" />
              </>
            )}
          </button>
        </div>
      </form>

    </section>
  );
}
