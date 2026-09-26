import React, { useState } from 'react';
import {
  CircleAlert, Info, ShieldCheck, Eye, EyeOff, Undo2, ChevronDown, ChevronRight, ListTree
} from 'lucide-react';

// What the pipeline read from the document and what it didn't — built by
// core/document_coverage.py and returned as report.cobertura on upload.
// Blocking problems ("bloquea") keep Run disabled until each one is fixed in
// the .docx or marked "Ignorar"; notices ("bloquea": false) are informational.

const BLOCK_STYLES = {
  ok: { bar: 'bg-success', text: 'text-gray-200', label: 'Leído' },
  conocido: { bar: 'bg-gray-600', text: 'text-gray-400', label: 'No se sube (esperado)' },
  problema: { bar: 'bg-warning', text: 'text-warning', label: 'Sin asignar' },
};

function IssueRow({ issue, ignored, onToggleIgnore, onShowBlock }) {
  const blocking = issue.bloquea;
  const Icon = blocking ? CircleAlert : Info;
  const tone = ignored
    ? 'border-border bg-background/40 opacity-60'
    : blocking
      ? 'border-warning/40 bg-warning/5'
      : 'border-border bg-background/60';

  return (
    <li className={`rounded-lg border px-3 py-2.5 ${tone}`}>
      <div className="flex items-start gap-2.5">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${blocking && !ignored ? 'text-warning' : 'text-gray-400'}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white break-words">
            {issue.titulo}
            {ignored && <span className="ml-2 text-[10px] font-normal text-gray-500">(ignorado)</span>}
            {!blocking && !ignored && <span className="ml-2 text-[10px] font-normal text-gray-500">(aviso, no bloquea)</span>}
          </p>
          <p className="text-xs text-gray-400 mt-1 leading-relaxed">{issue.detalle}</p>
          <div className="flex items-center gap-3 mt-2">
            {issue.bloque && (
              <button
                type="button"
                onClick={() => onShowBlock(issue.bloque)}
                className="flex items-center text-[11px] text-primary hover:underline"
              >
                <Eye className="w-3 h-3 mr-1" /> Ver contenido
              </button>
            )}
            <button
              type="button"
              onClick={() => onToggleIgnore(issue.id)}
              className="flex items-center text-[11px] text-gray-400 hover:text-white"
            >
              {ignored
                ? <><Undo2 className="w-3 h-3 mr-1" /> Deshacer</>
                : <><EyeOff className="w-3 h-3 mr-1" /> Ignorar</>}
            </button>
          </div>
        </div>
      </div>
    </li>
  );
}

function DocumentMap({ blocks, onShowBlock }) {
  const [open, setOpen] = useState(false);
  if (!blocks.length) return null;

  return (
    <div className="border-t border-border">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs font-semibold text-gray-300 hover:text-white"
      >
        <span className="flex items-center">
          <ListTree className="w-3.5 h-3.5 mr-2 text-primary" />
          Mapa del documento ({blocks.length} bloques)
        </span>
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
      {open && (
        <div className="px-4 pb-4">
          <div className="flex flex-wrap gap-3 mb-3 text-[10px] text-gray-500">
            {Object.entries(BLOCK_STYLES).map(([key, s]) => (
              <span key={key} className="flex items-center">
                <span className={`inline-block w-2 h-2 rounded-sm mr-1.5 ${s.bar}`} /> {s.label}
              </span>
            ))}
          </div>
          <ol className="space-y-1">
            {blocks.map((b) => {
              const s = BLOCK_STYLES[b.estado] || BLOCK_STYLES.conocido;
              const content = (
                <>
                  <span className={`w-1 self-stretch rounded-full shrink-0 ${s.bar}`} />
                  <span className={`flex-1 min-w-0 truncate text-[11px] ${s.text}`}>{b.titulo}</span>
                  <span className="text-[10px] text-gray-600 shrink-0">
                    {b.n_filas} fila{b.n_filas === 1 ? '' : 's'}
                  </span>
                </>
              );
              return (
                <li key={b.id}>
                  {b.estado === 'problema' ? (
                    <button
                      type="button"
                      onClick={() => onShowBlock(b.id)}
                      className="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-warning/10 text-left"
                    >
                      {content}
                    </button>
                  ) : (
                    <div className="flex items-center gap-2 px-2 py-1">{content}</div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function DocumentReviewPanel({ coverage, ignored, onToggleIgnore, onShowBlock }) {
  if (!coverage) return null;
  const issues = coverage.problemas || [];
  const blocks = coverage.bloques || [];
  const unresolved = issues.filter((p) => p.bloquea && !ignored.has(p.id));
  // Unresolved blocking problems first, then notices, then everything ignored.
  const order = (p) => (ignored.has(p.id) ? 2 : p.bloquea ? 0 : 1);
  const sorted = [...issues].sort((a, b) => order(a) - order(b));

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-md">
      <div className="p-4 bg-background border-b border-border flex items-center justify-between gap-3">
        <h3 className="font-semibold text-white">Revisión del documento</h3>
        {unresolved.length > 0 ? (
          <span className="flex items-center text-xs font-bold text-warning bg-warning/10 px-2 py-1 rounded border border-warning/20 shrink-0">
            <CircleAlert className="w-3.5 h-3.5 mr-1" />
            {unresolved.length} por resolver
          </span>
        ) : (
          <span className="flex items-center text-xs font-bold text-success bg-success/10 px-2 py-1 rounded border border-success/20 shrink-0">
            <ShieldCheck className="w-3.5 h-3.5 mr-1" />
            {issues.length === 0 ? 'Todo el contenido fue leído' : 'Sin problemas pendientes'}
          </span>
        )}
      </div>

      {issues.length > 0 ? (
        <div className="p-4">
          <p className="text-xs text-gray-400 mb-3">
            Compara lo que se leyó con la estructura esperada del documento. Cada problema se resuelve
            corrigiendo el .docx y volviéndolo a subir, o marcándolo como «Ignorar» si es intencional.
          </p>
          <ul className="space-y-2">
            {sorted.map((issue) => (
              <IssueRow
                key={issue.id}
                issue={issue}
                ignored={ignored.has(issue.id)}
                onToggleIgnore={onToggleIgnore}
                onShowBlock={onShowBlock}
              />
            ))}
          </ul>
        </div>
      ) : (
        <p className="p-4 text-xs text-gray-400">
          Cada parte del documento quedó asignada a una unidad, una actividad o una sección conocida.
        </p>
      )}

      <DocumentMap blocks={blocks} onShowBlock={onShowBlock} />
    </div>
  );
}
