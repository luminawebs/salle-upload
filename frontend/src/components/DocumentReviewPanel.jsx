import React, { useState } from 'react';
import {
  CircleAlert, Info, ShieldCheck, Eye, EyeOff, Undo2, ChevronDown, ChevronRight, ListTree,
  CheckCircle2, Plus, RefreshCw
} from 'lucide-react';

// What the pipeline read from the document and what it didn't — built by
// core/document_coverage.py and returned as report.cobertura on upload.
// Blocking problems ("bloquea") keep Run disabled until each one is fixed in
// the .docx or marked "Ignorar"; notices ("bloquea": false) are informational.

const BLOCK_STYLES = {
  ok: { bar: 'bg-success', text: 'text-gray-200', label: 'Leído' },
  corregido: { bar: 'bg-primary', text: 'text-primary', label: 'Añadido en la revisión' },
  conocido: { bar: 'bg-gray-600', text: 'text-gray-400', label: 'No se sube (esperado)' },
  problema: { bar: 'bg-warning', text: 'text-warning', label: 'Sin asignar' },
};

// Must match ACTIVITY_TYPES in core/document_coverage.py.
const ACTIVITY_TYPES = ['Foro', 'Tarea', 'Cuestionario'];

const controlClass = "bg-background border border-border rounded-md px-2 py-1 text-[11px] text-white focus:outline-none focus:border-primary disabled:opacity-50 max-w-full";
const actionClass = "flex items-center text-[11px] font-semibold px-2.5 py-1 rounded-md bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30 disabled:opacity-40 disabled:cursor-not-allowed";

// "Posible actividad no reconocida": turn the block into a new activity of the
// chosen type (core/document_corrections.py). Pre-selects the type the author
// marked with an X in the block's own "Herramientas…" row, when there is one.
function MakeActivityControl({ issue, busy, onChoice }) {
  const [tipo, setTipo] = useState(issue.tipo_sugerido || '');
  return (
    <div className="flex flex-wrap items-center gap-2 mt-2">
      <span className="text-[11px] text-gray-400 w-full sm:w-auto">Crear como actividad nueva:</span>
      <select value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={busy}
        aria-label="Tipo de actividad" className={controlClass}>
        <option value="">Tipo de actividad…</option>
        {ACTIVITY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <button type="button" onClick={() => onChoice(issue.id, { tipo })} disabled={!tipo || busy} className={actionClass}>
        {busy ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Plus className="w-3 h-3 mr-1" />}
        Crear actividad
      </button>
      {issue.tipo_sugerido && (
        <span className="text-[10px] text-gray-500">Sugerido por la «X» marcada en el documento</span>
      )}
    </div>
  );
}

// Any unassigned block: add its content to the end of an existing activity
// (e.g. questions that belong to a Cuestionario). Activities of the block's
// own unit are listed first; a Cuestionario with no questions is marked.
function AppendControl({ issue, activities = [], busy, onChoice }) {
  const [target, setTarget] = useState('');
  if (!activities.length) return null;
  const sameUnit = activities.filter((a) => a.unidad === issue.unidad);
  const others = activities.filter((a) => a.unidad !== issue.unidad);
  const label = (a) => `Actividad ${a.num} · ${a.tipo} (Unidad ${a.unidad})${a.sinPreguntas ? ' — sin preguntas' : ''}`;
  return (
    <div className="flex flex-wrap items-center gap-2 mt-2">
      <span className="text-[11px] text-gray-400 w-full sm:w-auto">O añadir a una actividad existente:</span>
      <select value={target} onChange={(e) => setTarget(e.target.value)} disabled={busy}
        aria-label="Actividad destino" className={controlClass}>
        <option value="">Actividad…</option>
        {sameUnit.length > 0 && others.length > 0 ? (
          <>
            <optgroup label={`Unidad ${issue.unidad}`}>
              {sameUnit.map((a) => <option key={a.num} value={a.num}>{label(a)}</option>)}
            </optgroup>
            <optgroup label="Otras unidades">
              {others.map((a) => <option key={a.num} value={a.num}>{label(a)}</option>)}
            </optgroup>
          </>
        ) : activities.map((a) => <option key={a.num} value={a.num}>{label(a)}</option>)}
      </select>
      <button type="button" onClick={() => onChoice(issue.id, { agregar_a: Number(target) })}
        disabled={!target || busy} className={actionClass}>
        {busy ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Plus className="w-3 h-3 mr-1" />}
        Añadir
      </button>
    </div>
  );
}

function ResolvedText({ resolved }) {
  if (resolved.accion === 'agregar') {
    return (
      <p className="text-xs text-primary mt-1 leading-relaxed">
        Su contenido se añadirá al final de la <b>Actividad {resolved.actividad}</b> y se subirá con ella.
      </p>
    );
  }
  return (
    <p className="text-xs text-primary mt-1 leading-relaxed">
      Se creará como <b>{resolved.tipo}</b> «{resolved.nombre}» en la Unidad {resolved.unidad} y se subirá su contenido.
    </p>
  );
}

const BLOCK_ISSUES = ['actividad_no_reconocida', 'contenido_sin_asignar'];

function IssueRow({ issue, ignored, busy, activities, onToggleIgnore, onShowBlock, onShowFragment, onChoice }) {
  const blocking = issue.bloquea;
  const resolved = issue.resuelto;
  const Icon = resolved ? CheckCircle2 : blocking ? CircleAlert : Info;
  const tone = resolved
    ? 'border-primary/40 bg-primary/5'
    : ignored
      ? 'border-border bg-background/40 opacity-60'
      : blocking
        ? 'border-warning/40 bg-warning/5'
        : 'border-border bg-background/60';
  const iconColor = resolved ? 'text-primary' : blocking && !ignored ? 'text-warning' : 'text-gray-400';
  const canChoose = BLOCK_ISSUES.includes(issue.tipo) && !resolved && !ignored;

  return (
    <li className={`rounded-lg border px-3 py-2.5 ${tone}`}>
      <div className="flex items-start gap-2.5">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${iconColor}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white break-words">
            {issue.titulo}
            {ignored && !resolved && <span className="ml-2 text-[10px] font-normal text-gray-500">(ignorado)</span>}
            {!blocking && !ignored && !resolved && <span className="ml-2 text-[10px] font-normal text-gray-500">(aviso, no bloquea)</span>}
          </p>
          {resolved ? <ResolvedText resolved={resolved} /> : (
            <p className="text-xs text-gray-400 mt-1 leading-relaxed">{issue.detalle}</p>
          )}
          {canChoose && issue.tipo === 'actividad_no_reconocida' && (
            <MakeActivityControl issue={issue} busy={busy} onChoice={onChoice} />
          )}
          {canChoose && (
            <AppendControl issue={issue} activities={activities} busy={busy} onChoice={onChoice} />
          )}
          <div className="flex items-center gap-3 mt-2">
            {resolved ? (
              <button type="button" onClick={() => onShowFragment(resolved)}
                className="flex items-center text-[11px] text-primary hover:underline">
                <Eye className="w-3 h-3 mr-1" /> Ver parseo
              </button>
            ) : issue.bloque && (
              <button type="button" onClick={() => onShowBlock(issue.bloque)}
                className="flex items-center text-[11px] text-primary hover:underline">
                <Eye className="w-3 h-3 mr-1" /> Ver contenido
              </button>
            )}
            {resolved ? (
              <button type="button" onClick={() => onChoice(issue.id, null)} disabled={busy}
                className="flex items-center text-[11px] text-gray-400 hover:text-white disabled:opacity-40">
                <Undo2 className="w-3 h-3 mr-1" /> Deshacer
              </button>
            ) : (
              <button type="button" onClick={() => onToggleIgnore(issue.id)}
                className="flex items-center text-[11px] text-gray-400 hover:text-white">
                {ignored
                  ? <><Undo2 className="w-3 h-3 mr-1" /> Deshacer</>
                  : <><EyeOff className="w-3 h-3 mr-1" /> Ignorar</>}
              </button>
            )}
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
                  {b.estado === 'problema' || b.estado === 'corregido' ? (
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

// A problem is settled once it's ignored or (for an unrecognized block)
// turned into an activity. Shared with AutomationView's Run gating.
export const isUnresolved = (issue, ignored) => issue.bloquea && !issue.resuelto && !ignored.has(issue.id);

export default function DocumentReviewPanel({
  coverage, activities = [], ignored, busyIssue, error, onToggleIgnore, onShowBlock, onShowFragment, onChoice
}) {
  if (!coverage) return null;
  const issues = coverage.problemas || [];
  const blocks = coverage.bloques || [];
  const unresolved = issues.filter((p) => isUnresolved(p, ignored));
  // Unresolved blocking problems first, then notices, then everything settled.
  const order = (p) => (p.resuelto || ignored.has(p.id) ? 2 : p.bloquea ? 0 : 1);
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
            corrigiendo el .docx y volviéndolo a subir, marcándolo como «Ignorar» si es intencional o,
            para un bloque sin asignar, creándolo como actividad nueva o añadiéndolo a una actividad existente.
          </p>
          {error && (
            <p className="mb-3 text-xs text-error bg-error/10 border border-error/30 rounded-lg px-3 py-2">{error}</p>
          )}
          <ul className="space-y-2">
            {sorted.map((issue) => (
              <IssueRow
                key={issue.id}
                issue={issue}
                ignored={ignored.has(issue.id)}
                busy={busyIssue !== null}
                activities={activities}
                onToggleIgnore={onToggleIgnore}
                onShowBlock={onShowBlock}
                onShowFragment={onShowFragment}
                onChoice={onChoice}
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
