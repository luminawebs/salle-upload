# Project Architecture & Workflow

This document visualizes the current automation workflow for the LA SALLE project and proposes an enhanced architecture integrating AI tools.

## Current Workflow

The current system relies on deterministic scripting (DOM traversal, Regex, and Mammoth) to parse DOCX files and Selenium to automate the Moodle UI.

```mermaid
graph TD
    %% Entities
    User((User))
    Moodle[(Moodle Platform)]
    
    %% Input Layer
    subgraph Input Phase
        Docx[Word Documents .docx]
        Images[Additional Assets/Images]
    end
    
    %% Core Processing Layer
    subgraph Core Processing
        Parser[core/data_parser.py<br>Mammoth DOCX to HTML]
        Splitter[Workflow Splitter<br>Separates Activities & Materials]
        Transformer[actions/html_transformer.py<br>Extracts Questions to Moodle XML]
    end
    
    %% Automation Layer
    subgraph Selenium Automation Layer
        Auth[moodle_actions.py<br>Login & Navigation]
        Pages[Puntos Extras & Pages Automation]
        Quiz[cuestionario_export_actions.py<br>Uploads XML & Updates Grades]
    end
    
    %% Flow
    User -->|Uploads| Docx
    User -->|Uploads| Images
    Docx --> Parser
    Parser --> Splitter
    Splitter -->|Course Material| Pages
    Splitter -->|Raw Questions HTML| Transformer
    Transformer -->|Moodle XML| Quiz
    
    Auth --> Moodle
    Pages -->|Creates Content| Moodle
    Quiz -->|Imports Questions & Assigns| Moodle
```

---

## Recommended AI-Enhanced Workflow

The proposed architecture integrates Large Language Models (LLMs) and computer vision to eliminate brittle regex/DOM parsing. AI acts as an intelligent middleware, transforming unstructured pedagogical documents into perfectly structured Moodle assets, while adding capabilities like automatic question generation and accessibility enhancements.

```mermaid
graph TD
    %% Entities
    User((User))
    Moodle[(Moodle Platform)]
    LLM{AI Language Model<br>e.g., Gemini 1.5 Pro}
    Vision{AI Vision Model}
    
    %% Input Layer
    subgraph Input Phase
        Docx[Word Documents .docx]
        Images[Additional Assets/Images]
    end
    
    %% AI Processing Layer
    subgraph Intelligent Processing Middleware
        Parser[Basic Text/HTML Extraction]
        
        AI_Extractor[AI Content Structurer<br>Prompts LLM to identify Activities, Material, and Questions]
        AI_Quiz_Gen[AI Question Generator<br>Optionally generates new questions from material]
        AI_Alt_Text[AI Accessibility<br>Generates Alt-Text for Images]
        
        Formatter[Moodle XML & HTML Formatter]
    end
    
    %% Automation Layer
    subgraph Selenium Automation Layer
        Auth[Login & Navigation]
        Pages[Dynamic Page Builder]
        Quiz[XML Uploader & Quiz Manager]
    end
    
    %% Flow
    User -->|Uploads| Docx
    User -->|Uploads| Images
    
    Docx --> Parser
    Images --> Vision
    Vision -->|Alt Text & Context| AI_Alt_Text
    
    Parser -->|Raw Text| AI_Extractor
    AI_Extractor -->|Structured JSON| Formatter
    
    %% AI Generative capabilities
    AI_Extractor -.->|Course Context| AI_Quiz_Gen
    AI_Quiz_Gen -.->|Supplemental Questions| Formatter
    
    AI_Alt_Text --> Formatter
    
    Formatter -->|Clean HTML Layouts| Pages
    Formatter -->|Perfect Moodle XML| Quiz
    
    Auth --> Moodle
    Pages --> Moodle
    Quiz --> Moodle
    
    classDef ai fill:#f9f,stroke:#333,stroke-width:2px;
    class LLM,Vision,AI_Extractor,AI_Quiz_Gen,AI_Alt_Text ai;
```

### Key AI Benefits:
1. **Robust Parsing (`AI Content Structurer`)**: Instead of relying on specific words like "Pregunta 1" or "Respuesta correcta", the LLM reads the document semantically. It can identify a question, its options, and the correct answer regardless of the author's formatting style.
2. **Accessibility (`AI Accessibility`)**: Vision models can automatically describe uploaded images and inject `alt` attributes into the HTML, fulfilling accessibility standards automatically.
3. **Generative Features (`AI Question Generator`)**: The system could read the "Material de Referencia" and automatically propose new quiz questions to the instructor.
