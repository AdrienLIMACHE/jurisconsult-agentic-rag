import React from 'react';
import { Scale, Dices, ExternalLink } from 'lucide-react';

export default function Navbar({ onRefreshRandom, loading }) {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-paper-300 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/60 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-ink-900 text-white flex items-center justify-center shadow-subtle">
            <Scale className="h-5 w-5 text-paper-100" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-serif text-lg font-semibold tracking-tight text-ink-950">
                JurisConsult AI
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded bg-paper-200 text-ink-600 border border-paper-300">
                TJ Paris
              </span>
            </div>
            <p className="text-[11px] font-medium text-ink-600">
              Fait par Limache Adrien et Anton Nelcon Steve
            </p>
          </div>
        </div>

        {/* Right Action */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onRefreshRandom}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium bg-paper-100 hover:bg-paper-200 text-ink-800 border border-paper-300 transition-all hover:shadow-subtle disabled:opacity-50"
            title="Tirer 6 nouvelles affaires au sort"
          >
            <Dices className={`h-3.5 w-3.5 text-ink-600 ${loading ? 'animate-spin' : ''}`} />
            <span>Tirer d'autres affaires 🎲</span>
          </button>

          <a
            href="https://www.legifrance.gouv.fr/judilibre"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex items-center gap-1 text-xs text-ink-400 hover:text-ink-900 transition-colors font-mono ml-1"
          >
            <span>Judilibre</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

      </div>
    </header>
  );
}
