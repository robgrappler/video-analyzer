#!/usr/bin/env python3
"""
Translate SRT subtitle files offline using Argos Translate.
Preserves timecodes and formatting while translating text content.

Usage:
    ./translate_srt.py input_es.srt [--from es] [--to en] [--output custom.srt]

Requirements:
    pip install argostranslate
    
    # Download Spanish→English model (one-time):
    python3 -c "
import argostranslate.package
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
pkg = next(p for p in available if p.from_code == 'es' and p.to_code == 'en')
argostranslate.package.install_from_path(pkg.download())
"
"""

import argparse
import re
import sys
from pathlib import Path


def parse_srt(content: str) -> list[dict]:
    """Parse SRT content into structured subtitle blocks."""
    blocks = []
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.*\n)*?)(?=\n\d+\n|\Z)'
    
    for match in re.finditer(pattern, content, re.MULTILINE):
        index, start, end, text = match.groups()
        blocks.append({
            'index': int(index),
            'start': start,
            'end': end,
            'text': text.strip()
        })
    
    return blocks


def translate_blocks(blocks: list[dict], from_lang: str, to_lang: str) -> list[dict]:
    """Translate text content of subtitle blocks."""
    try:
        import argostranslate.translate
    except ImportError:
        print("Error: argostranslate not installed", file=sys.stderr)
        print("Install with: pip install argostranslate", file=sys.stderr)
        sys.exit(1)
    
    # Get installed languages
    installed = argostranslate.translate.get_installed_languages()
    
    # Find source and target languages
    try:
        source = next(l for l in installed if l.code == from_lang)
        target = next(l for l in installed if l.code == to_lang)
    except StopIteration:
        print(f"Error: {from_lang}→{to_lang} model not installed", file=sys.stderr)
        print(f"\nInstall with:", file=sys.stderr)
        print(f"python3 -c \"", file=sys.stderr)
        print(f"import argostranslate.package", file=sys.stderr)
        print(f"argostranslate.package.update_package_index()", file=sys.stderr)
        print(f"available = argostranslate.package.get_available_packages()", file=sys.stderr)
        print(f"pkg = next(p for p in available if p.from_code == '{from_lang}' and p.to_code == '{to_lang}')", file=sys.stderr)
        print(f"argostranslate.package.install_from_path(pkg.download())", file=sys.stderr)
        print(f"\"", file=sys.stderr)
        sys.exit(1)
    
    # Get translator
    translation = source.get_translation(target)
    
    print(f"Translating {len(blocks)} subtitle blocks...", file=sys.stderr)
    
    # Translate each block
    translated = []
    for i, block in enumerate(blocks, 1):
        translated_text = translation.translate(block['text'])
        translated.append({
            **block,
            'text': translated_text
        })
        
        if i % 50 == 0:
            print(f"  {i}/{len(blocks)} blocks translated", file=sys.stderr)
    
    print(f"Translation complete!", file=sys.stderr)
    return translated


def format_srt(blocks: list[dict]) -> str:
    """Format subtitle blocks back into SRT format."""
    output = []
    for block in blocks:
        output.append(f"{block['index']}")
        output.append(f"{block['start']} --> {block['end']}")
        output.append(block['text'])
        output.append("")  # Blank line between blocks
    
    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Translate SRT subtitle files offline using Argos Translate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./translate_srt.py video_transcription_es.srt
  ./translate_srt.py input.srt --from es --to en --output translated.srt
  ./translate_srt.py spanish.srt --to en  # Auto-detects output filename
        """
    )
    
    parser.add_argument('input', type=Path, help='Input SRT file to translate')
    parser.add_argument('--from', dest='from_lang', default='es', 
                       help='Source language code (default: es)')
    parser.add_argument('--to', dest='to_lang', default='en',
                       help='Target language code (default: en)')
    parser.add_argument('--output', type=Path, help='Output SRT file (default: auto-generated)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    if args.input.suffix.lower() != '.srt':
        print(f"Warning: Input file doesn't have .srt extension", file=sys.stderr)
    
    # Determine output file
    if args.output:
        output_path = args.output
    else:
        # Auto-generate: replace _es.srt with _en.srt, or append _en
        stem = args.input.stem
        if stem.endswith(f'_{args.from_lang}'):
            stem = stem[:-len(f'_{args.from_lang}')]
        output_path = args.input.parent / f"{stem}_{args.to_lang}.srt"
    
    print(f"Input:  {args.input}", file=sys.stderr)
    print(f"Output: {output_path}", file=sys.stderr)
    print(f"Translation: {args.from_lang} → {args.to_lang}", file=sys.stderr)
    print("", file=sys.stderr)
    
    # Read input
    try:
        content = args.input.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = args.input.read_text(encoding='latin-1')
    
    # Parse SRT
    blocks = parse_srt(content)
    print(f"Parsed {len(blocks)} subtitle blocks", file=sys.stderr)
    
    if not blocks:
        print("Error: No subtitle blocks found in input file", file=sys.stderr)
        sys.exit(1)
    
    # Translate
    translated_blocks = translate_blocks(blocks, args.from_lang, args.to_lang)
    
    # Format and save
    output_content = format_srt(translated_blocks)
    output_path.write_text(output_content, encoding='utf-8')
    
    print(f"\nTranslated SRT saved to: {output_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
