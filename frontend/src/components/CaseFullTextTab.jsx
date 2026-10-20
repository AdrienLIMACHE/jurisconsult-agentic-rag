import React, { useState } from 'react';
import { Copy, Check, FileText, ScrollText } from 'lucide-react';

export default function CaseFullTextTab({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!text) {
    return (
      <div className="bg-white rounded-lg border border-paper-300 p-8 text-center text-ink-400">
        <ScrollText className="h-7 w-7 mx-auto mb-2 opacity-40" />
        <p className="text-xs font-mono">Chargement de la minute intégrale...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-subtle border border-paper-300 p-5 sm:p-6 space-y-4">
      
      {/* Action and Info Bar */}
      <div className="flex flex-wrap items-center justify-between text-xs pb-3 border-b border-paper-200 gap-2">
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-500">
          <ScrollText className="h-3.5 w-3.5 text-ink-400" />
          <span>Minute Officielle du Greffe</span>
          <span className="text-paper-400">•</span>
          <span>{text.length.toLocaleString('fr-FR')} caractères</span>
        </div>

        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-paper-100 hover:bg-paper-200 text-ink-800 transition font-mono text-xs border border-paper-300"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-court-emerald" /> : <Copy className="h-3.5 w-3.5 text-ink-400" />}
          <span>{copied ? 'Minute copiée' : 'Copier la minute intégrale'}</span>
        </button>
      </div>

      {/* Official Court Minute Body */}
      <div className="p-6 rounded bg-paper-50/70 border border-paper-300 text-ink-900 text-xs sm:text-[13px] leading-relaxed font-serif-legal whitespace-pre-wrap max-h-[540px] overflow-y-auto selection:bg-paper-300">
        {text}
      </div>

    </div>
  );
}
