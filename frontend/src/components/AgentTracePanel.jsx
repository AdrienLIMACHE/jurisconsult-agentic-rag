import React, { useState } from 'react';
import {
  GitBranch, Wrench, Eye, ShieldCheck, CheckCircle2,
  ChevronDown, ChevronRight, Clock, Cpu, Database, Globe
} from 'lucide-react';

const STEP_STYLES = {
  DECISION: {
    badgeBg: 'bg-violet-100 text-violet-900 border-violet-300',
    icon: GitBranch,
    label: 'DECISION',
  },
  TOOL: {
    badgeBg: 'bg-amber-100 text-amber-900 border-amber-300',
    icon: Wrench,
    label: 'TOOL',
  },
  OBSERVATION: {
    badgeBg: 'bg-sky-100 text-sky-900 border-sky-300',
    icon: Eye,
    label: 'OBSERVATION',
  },
  CHECK: {
    badgeBg: 'bg-emerald-100 text-emerald-900 border-emerald-300',
    icon: ShieldCheck,
    label: 'CHECK',
  },
  FINAL: {
    badgeBg: 'bg-neutral-900 text-white border-neutral-800',
    icon: CheckCircle2,
    label: 'FINAL',
  },
};

export default function AgentTracePanel({ trace = [], metrics = null, verificationStatus = 'SUFFISANT' }) {
  const [expanded, setExpanded] = useState(true);

  if (!trace || trace.length === 0) {
    return null;
  }

  const isSufficient = verificationStatus === 'SUFFISANT';

  return (
    <div className="mt-3 rounded-xl border border-paper-300 bg-white overflow-hidden shadow-subtle">
      {/* Header cliquable de la trace Agentique */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3.5 py-2 bg-paper-100/90 hover:bg-paper-200/70 flex items-center justify-between text-left transition-colors border-b border-paper-200"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-ink-900 text-white">
            <GitBranch className="h-3 w-3" />
            <span>Trace LangGraph ({trace.length} étapes)</span>
          </span>

          <span
            className={`inline-flex items-center gap-1 font-mono text-[10px] font-semibold px-2 py-0.5 rounded border ${
              isSufficient
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-amber-50 text-amber-900 border-amber-200'
            }`}
          >
            <ShieldCheck className="h-3 w-3" />
            <span>CHECK : {verificationStatus}</span>
          </span>

          {metrics && (
            <span className="text-[10px] font-mono text-ink-500 flex items-center gap-1">
              <Clock className="h-2.5 w-2.5" />
              <span>{metrics.latency_s}s</span>
              <span>•</span>
              <span>{metrics.iterations} itér.</span>
              <span>•</span>
              <span>{metrics.llm_calls} LLM</span>
            </span>
          )}
        </div>

        <div className="text-ink-500">
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </div>
      </button>

      {/* Corps détaillé des étapes du graphe */}
      {expanded && (
        <div className="p-3 space-y-2 bg-[#FCFCFA] text-[11px]">
          {/* Barre de métriques d'observabilité (Bonus TP3) */}
          {metrics && (
            <div className="flex flex-wrap items-center gap-2 pb-2 mb-1 border-b border-paper-200 font-mono text-[10px] text-ink-600">
              <span className="inline-flex items-center gap-1 bg-white px-2 py-0.5 rounded border border-paper-200">
                <Wrench className="h-2.5 w-2.5 text-amber-700" />
                <span>Outils : {(metrics.tools_used || []).join(' → ') || 'aucun'}</span>
              </span>
              <span className="inline-flex items-center gap-1 bg-emerald-50/70 text-emerald-900 px-2 py-0.5 rounded border border-emerald-200">
                <Database className="h-2.5 w-2.5" />
                <span>[CORPUS_TP2] : {metrics.corpus_docs_count || 0}</span>
              </span>
              <span className="inline-flex items-center gap-1 bg-indigo-50/70 text-indigo-900 px-2 py-0.5 rounded border border-indigo-200">
                <Globe className="h-2.5 w-2.5" />
                <span>[SOURCE_EXTERNE] : {metrics.external_docs_count || 0}</span>
              </span>
              <span className="inline-flex items-center gap-1 bg-white px-2 py-0.5 rounded border border-paper-200">
                <Cpu className="h-2.5 w-2.5 text-ink-500" />
                <span>Appels LLM : {metrics.llm_calls}</span>
              </span>
            </div>
          )}

          {/* Liste séquentielle des étapes : DECISION -> TOOL -> OBSERVATION -> CHECK -> FINAL */}
          <div className="space-y-1.5">
            {trace.map((step, idx) => {
              const style = STEP_STYLES[step.step_type] || STEP_STYLES.DECISION;
              const StepIcon = style.icon;
              return (
                <div
                  key={idx}
                  className="p-2 rounded-lg bg-white border border-paper-200 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`inline-flex items-center gap-1 font-mono text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${style.badgeBg}`}
                      >
                        <StepIcon className="h-2.5 w-2.5" />
                        <span>[{style.label}]</span>
                      </span>
                      <span className="font-mono font-semibold text-ink-900 text-[11px]">
                        {step.title}
                      </span>
                    </div>
                    <span className="font-mono text-[9px] text-ink-400">
                      itér. #{step.iteration || 1} • {step.timestamp_ms || 0} ms
                    </span>
                  </div>
                  {step.detail && (
                    <p className="text-[11px] text-ink-600 font-mono leading-snug pl-1 border-l-2 border-paper-300 whitespace-pre-wrap">
                      {step.detail}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
