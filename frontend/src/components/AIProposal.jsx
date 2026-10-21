import React, { useEffect, useState } from 'react';
import { Sparkles, RefreshCw, AlertTriangle, Check, X, Undo2, Info } from 'lucide-react';
import { QuestionCard } from './ActivityPreview';

const API_BASE = import.meta.env.VITE_API_BASE || "";

// "Revisión con IA" of one quiz: what the AI found that the question reader
// didn't, as proposals the user accepts or discards one by one. Only accepted
// proposals change the upload (core/ai_question_review.py); everything shown
// was verified word for word against the document first.

const LEVELS = {
  pregunta: 'solo las preguntas en duda',
  bloque: 'el bloque de preguntas',
  actividad: 'la actividad completa',
};

function Evidence({ q }) {
  if (!q?.evidencia) return null;
  return (
    <p className="text-[11px] text-gray-400">
      Según el documento: <span className="text-gray-200">«{q.evidencia}»</span>
    </p>
  );
}

function ProposalItem({ item, busy, onDecide }) {
  const decided = item.decision;
  const tone = !item.aceptable
    ? 'border-border bg-background/40'
    : decided === 'aceptar'
      ? 'border-success/40 bg-success/5'
      : decided === 'descartar'
        ? 'border-border bg-background/40 opacity-70'
        : 'border-primary/40 bg-primary/5';

  return (
    <li className={`rounded-lg border p-4 space-y-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">{item.etiqueta}</p>
        {decided && (
          <span className={`text-[11px] font-semibold ${decided === 'aceptar' ? 'text-success' : 'text-gray-400'}`}>
            {decided === 'aceptar' ? 'Aceptada: se subirá así' : 'Descartada: no cambia nada'}
          </span>
        )}
      </div>
      {item.nota && (
        <p className="flex items-start text-xs text-gray-400">
          <Info className="w-3.5 h-3.5 mr-1.5 mt-0.5 shrink-0" /> {item.nota}
        </p>
      )}

      <div className={`grid gap-3 ${item.antes && item.despues ? 'lg:grid-cols-2' : ''}`}>
        {item.antes && (
          <div className="space-y-1.5 min-w-0">
            <p className="text-[11px] uppercase tracking-wide text-gray-500">Lo que lee el sistema hoy</p>
            <QuestionCard q={item.antes} title={`Pregunta ${item.antes.numero}`} />
          </div>
        )}
        {item.despues && (
          <div className="space-y-1.5 min-w-0">
            <p className="text-[11px] uppercase tracking-wide text-gray-500">Propuesta de la IA</p>
            <QuestionCard q={item.despues} title={item.tipo === 'nueva' ? 'Pregunta nueva' : item.tipo === 'info' ? 'Lectura de la IA' : 'Con la propuesta'} />
            <Evidence q={item.despues} />
          </div>
        )}
      </div>

      {item.aceptable && (
        <div className="flex flex-wrap gap-2">
          {decided ? (
            <button type="button" disabled={busy} onClick={() => onDecide({ [item.id]: null })}
              className="flex items-center text-xs text-gray-400 hover:text-white disabled:opacity-40">
              <Undo2 className="w-3.5 h-3.5 mr-1" /> Cambiar decisión
            </button>
          ) : (
            <>
              <button type="button" disabled={busy} onClick={() => onDecide({ [item.id]: 'aceptar' })}
                className="flex items-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-success/15 border border-success/40 text-success hover:bg-success/25 disabled:opacity-40">
                <Check className="w-3.5 h-3.5 mr-1" /> Aceptar
              </button>
              <button type="button" disabled={busy} onClick={() => onDecide({ [item.id]: 'descartar' })}
                className="flex items-center text-xs px-3 py-1.5 rounded-lg border border-border text-gray-300 hover:text-white disabled:opacity-40">
                <X className="w-3.5 h-3.5 mr-1" /> Descartar
              </button>
            </>
          )}
        </div>
      )}
    </li>
  );
}

export default function AIProposal({ courseId, category, filename, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ course_id: courseId, category, filename });
    fetch(`${API_BASE}/api/ai-proposal?${params}`)
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || 'No se pudo cargar la revisión con IA.');
        return body;
      })
      .then((body) => { if (!cancelled) setData(body); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [courseId, category, filename]);

  const post = async (url, payload, setFlag) => {
    setFlag(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, category, filename, ...payload }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || 'No se pudo completar la acción.');
      setData(body);
      if (body.report) onChanged?.(body.report);
    } catch (err) {
      setError(err.message);
    } finally {
      setFlag(false);
    }
  };

  const decide = (decisiones) => post('/api/ai-decisions', { decisiones }, setBusy);
  const askAI = () => post('/api/ai-proposal', {}, setRunning);

  if (!data && !error) {
    return (
      <div className="flex items-center justify-center py-10 text-sm text-gray-400">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Cargando...
      </div>
    );
  }

  const proposal = data?.propuesta;
  const errorBox = error && (
    <p className="flex items-start text-xs text-error bg-error/10 border border-error/30 rounded-lg px-3 py-2">
      <AlertTriangle className="w-3.5 h-3.5 mr-1.5 mt-0.5 shrink-0" /> {error}
    </p>
  );

  if (!proposal) {
    return (
      <div className="space-y-3">
        {errorBox}
        {data && data.brechas.length === 0 ? (
          <p className="text-sm text-gray-400">
            El sistema ya lee todas las preguntas de esta actividad con su respuesta: no hay nada que revisar con la IA.
          </p>
        ) : data && !data.disponible ? (
          <p className="text-sm text-gray-400">La revisión con IA no está disponible. {data.motivo}</p>
        ) : data && (
          <div className="rounded-lg border border-border bg-background p-4 space-y-3">
            <p className="text-sm text-gray-300">
              El sistema no pudo leer bien algunas preguntas de esta actividad. La IA puede leerla y proponer los
              cambios; tú decides cuáles aceptar. Solo se muestra lo que aparece palabra por palabra en el documento,
              y nada cambia en Moodle sin tu aprobación.
            </p>
            {running ? (
              <p className="flex items-center text-sm text-primary">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                La IA está leyendo la actividad. Puede tardar uno o dos minutos…
              </p>
            ) : (
              <button type="button" onClick={askAI}
                className="flex items-center text-sm font-semibold px-4 py-2 rounded-lg bg-primary text-white hover:bg-primary/90">
                <Sparkles className="w-4 h-4 mr-2" /> Revisar con la IA
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  const pending = proposal.items.filter((it) => it.aceptable && !it.decision);
  return (
    <div className="space-y-4">
      {errorBox}
      <div className="rounded-lg border border-border bg-background px-4 py-3 space-y-1">
        <p className="flex items-center text-sm text-white">
          <Sparkles className="w-4 h-4 mr-2 text-primary" />
          La IA leyó {LEVELS[proposal.nivel] || 'la actividad'} y encontró {proposal.preguntas_ia} pregunta{proposal.preguntas_ia === 1 ? '' : 's'}.
        </p>
        <p className="text-xs text-gray-400">
          Todo lo que ves aquí existe palabra por palabra en el documento. {proposal.aceptadas} aceptada{proposal.aceptadas === 1 ? '' : 's'} · {proposal.pendientes} por decidir.
        </p>
      </div>

      {proposal.items.length === 0 ? (
        <p className="text-sm text-gray-400">La IA no encontró nada que cambiar en lo que lee el sistema.</p>
      ) : (
        <>
          {pending.length > 1 && (
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={busy}
                onClick={() => decide(Object.fromEntries(pending.map((it) => [it.id, 'aceptar'])))}
                className="flex items-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-success/15 border border-success/40 text-success hover:bg-success/25 disabled:opacity-40">
                <Check className="w-3.5 h-3.5 mr-1" /> Aceptar las {pending.length} pendientes
              </button>
            </div>
          )}
          <ul className="space-y-3">
            {proposal.items.map((it) => <ProposalItem key={it.id} item={it} busy={busy} onDecide={decide} />)}
          </ul>
        </>
      )}
    </div>
  );
}
