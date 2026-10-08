import React, { useEffect, useState } from 'react';
import { ArrowLeft, RefreshCw, AlertTriangle, Copy, Check, Code2, Info } from 'lucide-react';
import { QuestionCard } from './ActivityPreview';

const API_BASE = import.meta.env.VITE_API_BASE || "";

// "Formatos de preguntas": how to write each question type in the document.
// Every example comes from core/question_types/catalog.py and is read by the
// real parser when this page loads, so the right-hand side is exactly what the
// upload would do with it today (tests/test_question_formats.py guards it).

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked (http, permissions): the text stays selectable.
    }
  };
  return (
    <button type="button" onClick={copy} className="flex items-center text-[11px] text-gray-400 hover:text-white">
      {copied ? <Check className="w-3.5 h-3.5 mr-1 text-success" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
      {copied ? 'Copiado' : 'Copiar'}
    </button>
  );
}

function Variant({ variant }) {
  const [showXml, setShowXml] = useState(false);
  const q = variant.preguntas[0];

  return (
    <section className="space-y-3">
      <h4 className="text-sm font-semibold text-white">{variant.titulo}</h4>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[11px] uppercase tracking-wide text-gray-500">Así se escribe en el documento</p>
            <CopyButton text={variant.lineas.join('\n')} />
          </div>
          <div className="rounded-lg border border-border bg-background px-4 py-3 text-sm text-gray-200 space-y-1 font-serif">
            {variant.lineas.map((line, i) => <p key={i}>{line}</p>)}
          </div>
        </div>
        <div className="space-y-1.5">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Así lo lee el sistema</p>
          {q ? (
            <QuestionCard q={q} title="Vista previa" />
          ) : (
            <p className="flex items-start text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 mr-1.5 mt-0.5 shrink-0" />
              El sistema no reconoce este ejemplo. Avisa al equipo técnico.
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={() => setShowXml(!showXml)}
        aria-expanded={showXml}
        className="flex items-center text-[11px] text-gray-500 hover:text-white"
      >
        <Code2 className="w-3.5 h-3.5 mr-1" /> {showXml ? 'Ocultar' : 'Ver'} el XML que se importa en Moodle
      </button>
      {showXml && (
        <pre className="text-[11px] text-gray-300 bg-background border border-border rounded-lg p-3 overflow-x-auto custom-scrollbar">{variant.xml}</pre>
      )}
    </section>
  );
}

export default function QuestionFormatsPage({ onBack }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/question-formats`)
      .then(async (res) => {
        if (!res.ok) throw new Error('No se pudieron cargar los formatos.');
        return res.json();
      })
      .then((body) => {
        if (cancelled) return;
        setData(body);
        setSelected(body.formatos[0]?.id ?? null);
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  const format = data?.formatos.find((f) => f.id === selected);

  return (
    <div className="max-w-6xl mx-auto w-full space-y-5">
      <button type="button" onClick={onBack} className="flex items-center text-xs text-gray-400 hover:text-white">
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Volver a la carga del curso
      </button>

      <div>
        <h2 className="text-lg font-bold text-white">Formatos de preguntas</h2>
        <p className="text-sm text-gray-400 mt-1">
          Cómo escribir cada tipo de pregunta en el documento para que se suba bien a Moodle.
          Los ejemplos se leen con el sistema actual cada vez que abres esta página.
        </p>
      </div>

      {error && (
        <p className="flex items-start text-sm text-error bg-error/10 border border-error/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-4 h-4 mr-2 mt-0.5 shrink-0" /> {error}
        </p>
      )}

      {!data && !error && (
        <div className="flex items-center text-sm text-gray-400 py-10 justify-center">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Cargando formatos...
        </div>
      )}

      {data && (
        <>
          <div className="rounded-lg border border-border bg-surface px-4 py-3">
            <p className="flex items-center text-xs font-semibold text-gray-300 mb-1.5">
              <Info className="w-3.5 h-3.5 mr-1.5" /> Para todos los tipos
            </p>
            <ul className="list-disc pl-5 space-y-1 text-xs text-gray-400">
              {data.reglas.map((rule, i) => <li key={i}>{rule}</li>)}
            </ul>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-5">
            <nav className="flex md:flex-col gap-1.5 overflow-x-auto md:overflow-visible" aria-label="Tipos de pregunta">
              {data.formatos.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setSelected(f.id)}
                  aria-current={selected === f.id ? 'true' : undefined}
                  className={`text-left text-xs px-3 py-2 rounded-lg border whitespace-nowrap md:whitespace-normal transition-colors ${selected === f.id ? 'bg-primary/20 border-primary/40 text-primary' : 'border-border text-gray-400 hover:text-white'}`}
                >
                  {f.nombre}
                </button>
              ))}
            </nav>

            {format && (
              <article className="space-y-6 min-w-0">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-bold text-white">{format.nombre}</h3>
                    <span className="text-[10px] text-gray-400 border border-border rounded px-1.5 py-0.5">
                      En Moodle: {format.moodle}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 mt-1">{format.descripcion}</p>
                  {format.notas.length > 0 && (
                    <ul className="list-disc pl-5 mt-2 space-y-0.5 text-xs text-gray-500">
                      {format.notas.map((n, i) => <li key={i}>{n}</li>)}
                    </ul>
                  )}
                </div>
                {format.variantes.map((v) => <Variant key={v.titulo} variant={v} />)}
              </article>
            )}
          </div>
        </>
      )}
    </div>
  );
}
