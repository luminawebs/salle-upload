import React, { useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle, ChevronLeft, ChevronRight, Check } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || "";

// "Vista previa" of one activity, ordered: a tab per section ("¿Qué vamos a
// lograr?", "¿Cómo lo vamos a lograr?", …) and, for quizzes, a "Preguntas" tab
// with numbered buttons — each question exactly as the Moodle export reads it
// (built by core/activity_preview.py), so what's checked here is what uploads.

const QUESTION_TAB = '__preguntas__';
const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
const TYPE_LABELS = {
  multichoice: 'Opción múltiple',
  verdadero_falso: 'Verdadero / Falso',
  truefalse: 'Verdadero / Falso',
  cloze: 'Completar',
  drag_drop: 'Arrastrar y soltar',
};

// A multiple-choice / true-false question with no options, or none marked
// correct, would upload to Moodle with nothing right to choose (with no
// options it becomes a plain text item). Other types (completar, arrastrar)
// mark answers inside the text, so they're not judged here.
const answerProblem = (q) => {
  if (!['multichoice', 'verdadero_falso', 'truefalse'].includes(q.tipo)) return null;
  if (q.opciones.length === 0) return 'Sin opciones: en Moodle se subirá como texto, no como pregunta. Puede ser un párrafo leído como pregunta por error.';
  if (q.correctas === 0) return 'Ninguna opción está marcada como correcta: en Moodle esta pregunta no tendrá respuesta válida.';
  return null;
};
const hasAnswerProblem = (q) => answerProblem(q) !== null;

function Html({ html }) {
  return (
    <div
      className="prose prose-invert prose-sm max-w-none"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function QuestionsView({ questions, summary }) {
  const [index, setIndex] = useState(0);
  const q = questions[index];
  const withProblems = questions.filter(hasAnswerProblem).length;
  const missing = summary && summary.esperadas > summary.encontradas ? summary.esperadas - summary.encontradas : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400">
        <span><b className="text-gray-200">{questions.length}</b> pregunta{questions.length === 1 ? '' : 's'} se subirán</span>
        {withProblems > 0 && (
          <span className="text-warning">{withProblems} con problemas (en naranja)</span>
        )}
        {missing > 0 && (
          <span className="text-warning">faltan {missing} por leer (ver «Revisión del documento»)</span>
        )}
      </div>

      {questions.length === 0 ? (
        <p className="flex items-start text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 mr-1.5 mt-0.5 shrink-0" />
          No se reconoció ninguna pregunta en esta actividad.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Preguntas">
            {questions.map((item, i) => {
              const selected = i === index;
              const problem = hasAnswerProblem(item);
              return (
                <button
                  key={item.numero}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  onClick={() => setIndex(i)}
                  title={problem ? answerProblem(item) : `Pregunta ${item.numero}`}
                  className={`w-8 h-8 rounded-md text-xs font-semibold border transition-colors ${
                    selected
                      ? 'bg-primary border-primary text-white'
                      : problem
                        ? 'bg-warning/10 border-warning/50 text-warning hover:bg-warning/20'
                        : 'bg-background border-border text-gray-300 hover:border-gray-500 hover:text-white'
                  }`}
                >
                  {item.numero}
                </button>
              );
            })}
          </div>

          <div className="bg-background rounded-lg border border-border p-4 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-bold text-white">Pregunta {q.numero} de {questions.length}</h4>
              <span className="text-[10px] text-gray-500 uppercase tracking-wide">{TYPE_LABELS[q.tipo] || q.tipo}</span>
            </div>

            <Html html={q.enunciado_html} />

            {q.opciones.length > 0 && (
              <ol className="space-y-1.5">
                {q.opciones.map((o, i) => (
                  <li
                    key={i}
                    className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${o.correcta ? 'border-success/50 bg-success/10' : 'border-border'}`}
                  >
                    {/* Options that already start with their own letter ("A. …") keep it. */}
                    {!/^\s*[A-Ea-e][.)]\s/.test(o.html.replace(/<[^>]+>/g, '')) && (
                      <span className="text-xs font-semibold text-gray-500 mt-0.5 w-4 shrink-0">{LETTERS[i]})</span>
                    )}
                    <div className="flex-1 min-w-0"><Html html={o.html} /></div>
                    {o.correcta && (
                      <span className="flex items-center text-[10px] font-semibold text-success shrink-0 mt-0.5">
                        <Check className="w-3 h-3 mr-0.5" /> Correcta
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            )}

            {hasAnswerProblem(q) && (
              <p className="flex items-start text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg px-3 py-2">
                <AlertTriangle className="w-3.5 h-3.5 mr-1.5 mt-0.5 shrink-0" />
                {answerProblem(q)}
              </p>
            )}

            {Object.entries(q.retroalimentacion || {}).map(([kind, html]) => (
              <div key={kind} className="text-xs border-t border-border pt-3">
                <p className="text-gray-500 mb-1">
                  Retroalimentación{kind === 'correct' ? ' (correcta)' : kind === 'incorrect' ? ' (incorrecta)' : ''}
                </p>
                <Html html={html} />
              </div>
            ))}

            <div className="flex justify-between pt-1">
              <button type="button" onClick={() => setIndex(index - 1)} disabled={index === 0}
                className="flex items-center text-xs text-gray-400 hover:text-white disabled:opacity-30">
                <ChevronLeft className="w-4 h-4" /> Anterior
              </button>
              <button type="button" onClick={() => setIndex(index + 1)} disabled={index === questions.length - 1}
                className="flex items-center text-xs text-gray-400 hover:text-white disabled:opacity-30">
                Siguiente <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function ActivityPreview({ courseId, category, filename }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ course_id: courseId, category, filename });
    fetch(`${API_BASE}/api/activity-preview?${params}`)
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || 'No se pudo cargar la vista previa.');
        return body;
      })
      .then((body) => {
        if (cancelled) return;
        setData(body);
        const hasQuestions = body.preguntas.length > 0 || (body.resumen_preguntas?.esperadas || 0) > 0;
        setTab(hasQuestions ? QUESTION_TAB : (body.secciones[0]?.titulo ?? null));
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [courseId, category, filename]);

  if (error) {
    return (
      <div className="p-3 rounded-lg bg-error/10 border border-error/30 flex items-start text-error text-sm">
        <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" /> <span>{error}</span>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-gray-400">
        <RefreshCw className="w-6 h-6 animate-spin mb-2" />
        <p className="text-sm">Cargando vista previa...</p>
      </div>
    );
  }

  const hasQuestions = data.preguntas.length > 0 || (data.resumen_preguntas?.esperadas || 0) > 0;
  const tabs = [
    ...(hasQuestions ? [{ id: QUESTION_TAB, label: `Preguntas (${data.preguntas.length})` }] : []),
    ...data.secciones.map((s) => ({ id: s.titulo, label: s.titulo })),
  ];
  const section = data.secciones.find((s) => s.titulo === tab);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5 border-b border-border pb-3" role="tablist" aria-label="Secciones de la actividad">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${tab === t.id ? 'bg-primary/20 border-primary/40 text-primary' : 'border-border text-gray-400 hover:text-white'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === QUESTION_TAB ? (
        <QuestionsView questions={data.preguntas} summary={data.resumen_preguntas} />
      ) : section ? (
        section.html.trim()
          ? <div className="bg-background rounded-lg border border-border p-4"><Html html={section.html} /></div>
          : <p className="text-xs text-gray-500">Esta sección está vacía en el documento.</p>
      ) : (
        <p className="text-xs text-gray-500">No se reconocieron secciones en esta actividad.</p>
      )}
    </div>
  );
}
