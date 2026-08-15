# Guía de Pruebas: Nuevos Formatos de Preguntas

Este documento contiene instrucciones y ejemplos listos para copiar y pegar en tu documento de Word (`.docx`). El objetivo es que puedas probar fácilmente que el conversor a Moodle XML está procesando correctamente los nuevos tipos de preguntas.

---

## 1. Completar la Frase (Cloze)

**Instrucciones:**
1. Copia el bloque de abajo en tu documento de Word.
2. Asegúrate de incluir la línea `Tipo: completar`.
3. Usa corchetes `[ ]` alrededor de las palabras que el estudiante debe escribir.
4. Puedes usar `[Respuesta]` o `[=Respuesta]` indistintamente.

**Ejemplo para copiar:**

Pregunta 1:
Tipo: completar
El autor de la obra "Cien años de soledad" es [Gabriel García Márquez].

Retroalimentación correcta: ¡Excelente! Es uno de los autores más reconocidos del realismo mágico.
Retroalimentación incorrecta: Revisa tus apuntes sobre literatura latinoamericana.

---

## 2. Arrastrar y Soltar en el texto (Drag & Drop)

**Instrucciones:**
1. Copia el bloque de abajo en tu documento de Word.
2. Asegúrate de incluir la línea `Tipo: arrastrar_soltar`.
3. En el texto de la pregunta, usa corchetes dobles numéricos `[[1]]`, `[[2]]`, etc. para indicar dónde irán los espacios en blanco.
4. Escribe `Opciones:` y luego lista tus opciones debajo.
5. Usa el signo `=` antes de las respuestas correctas. El orden en que las pongas corresponderá a los números `[[1]]`, `[[2]]`, etc.
6. Cualquier opción sin el signo `=` será tratada como un **distractor** (una opción extra para confundir al estudiante).
7. Moodle barajará (*shuffle*) estas opciones automáticamente al mostrar el examen.

**Ejemplo para copiar:**

Pregunta 2:
Tipo: arrastrar_soltar
La capital de Francia es [[1]], mientras que la capital de España es [[2]].

Opciones:
=París
=Madrid
Londres
Berlín

Retroalimentación: París y Madrid son las capitales correctas, mientras que Londres y Berlín actúan como distractores en esta pregunta.

---

## 3. Verdadero o Falso (Con declaración de Tipo explícita)

**Instrucciones:**
Aunque el sistema detecta Verdadero/Falso automáticamente, ahora también puedes forzarlo escribiendo el tipo explícitamente para mayor seguridad.

**Ejemplo para copiar:**

Pregunta 3:
Tipo: verdadero_falso
El Sol gira alrededor de la Tierra.

Opciones:
Verdadero
=Falso

---

## Pasos para la validación:
1. Pega los 3 ejemplos anteriores en un documento de Word y guárdalo.
2. Corre tu proceso normal de conversión (`html_transformer.py` o sube el docx a la plataforma).
3. Importa el archivo `questions.xml` resultante en un curso de prueba en Moodle.
4. Haz una "Vista previa" de las preguntas importadas y valida que:
   - La Pregunta 1 tenga una caja de texto para escribir.
   - La Pregunta 2 tenga cajas arrastrables (incluyendo Londres y Berlín) que encajen en los huecos del texto.
   - La Pregunta 3 sea del tipo Verdadero/Falso clásico.
