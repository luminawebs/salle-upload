#!/usr/bin/env python
"""
Diagnostic script to validate pregunta export mapping.
Tests with ENABLE_INFOGRAFIA_EXPORT=True.
"""
from pathlib import Path
from actions.infografia_parser import parse_infografia_html, generate_infografia_html
from config.settings import Config

# Ensure export is enabled
print(f"ENABLE_INFOGRAFIA_EXPORT: {Config.ENABLE_INFOGRAFIA_EXPORT}\n")

# Parse raw HTML
raw_path = Path('assets/raw/VIR-INFOGRAFIA07.html')
raw_html = raw_path.read_text('utf-8')
parsed = parse_infografia_html(raw_html)

print("=" * 80)
print("PARSED SLIDES SUMMARY")
print("=" * 80)
for i, slide in enumerate(parsed['slides']):
    print(f"\n[{i}] Type: {slide['type']:<10} | Slide#: {str(slide.get('slide_number', 'N/A')):<5} | Title: {slide['title'][:60]}")
    if slide['type'] == 'pregunta':
        print(f"     Options: {len(slide.get('options', []))} | Content lines: {len(slide.get('content', []))}")

print("\n" + "=" * 80)
print("PREGUNTA SLIDE NUMBERS")
print("=" * 80)
pregunta_indices = []
for i, s in enumerate(parsed['slides']):
    if s['type'] == 'pregunta':
        slide_num = s.get('slide_number')
        pregunta_indices.append((i, slide_num))
        print(f"List index {i}: Pregunta with slide_number={slide_num}")

print("\n" + "=" * 80)
print("INFO SLIDE NUMBERS")
print("=" * 80)
info_indices = []
for i, s in enumerate(parsed['slides']):
    if s['type'] == 'info':
        slide_num = s.get('slide_number')
        info_indices.append((i, slide_num))
        print(f"List index {i}: Info with slide_number={slide_num}")

print("\n" + "=" * 80)
print("EXPECTED MATCHING (Pregunta should match Info by slide_number)")
print("=" * 80)
for info_idx, info_num in info_indices:
    for pregunta_idx, pregunta_num in pregunta_indices:
        if info_num == pregunta_num:
            print(f"✓ Info Slide {info_num} (index {info_idx}) should have Pregunta {pregunta_num} (index {pregunta_idx})")

print("\n" + "=" * 80)
print("GENERATING EXPORT HTML")
print("=" * 80)
html = generate_infografia_html(
    parsed, 
    'https://contenidomoodle.s3.amazonaws.com/UNIMINUTO_VIRTUAL/pregrado/COMMARINT/', 
    7, 
    'Course', 
    'Presentation', 
    parsed['infografia_subtitle']
)

print(f"Generated HTML length: {len(html)} chars")
print(f"Contains 'Pregunta 1': {'Pregunta 1' in html}")
print(f"Contains 'Pregunta 2': {'Pregunta 2' in html}")
print(f"Contains 'virtual-info-quiz': {'virtual-info-quiz' in html}")
print(f"Contains 'data-correct': {'data-correct' in html}")
print(f"Contains type=\"radio\": {'type=\"radio\"' in html}")

# Count quiz occurrences
quiz_count = html.count('virtual-info-quiz')
print(f"Quiz divs found: {quiz_count}")

# Save for inspection
output_path = Path('test_export_output.html')
output_path.write_text(html, 'utf-8')
print(f"\nExport HTML saved to: {output_path}")

print("\n" + "=" * 80)
print("INSPECTION: Look for 'Pregunta' sections in generated HTML")
print("=" * 80)
lines = html.split('\n')
for i, line in enumerate(lines):
    if 'Pregunta' in line or 'virtual-info-quiz' in line or 'data-correct' in line:
        # Print context
        start = max(0, i - 1)
        end = min(len(lines), i + 3)
        print(f"Line {i}: {line.strip()[:100]}")
