"""
Utilitários para extração de texto de PDFs via Docling.

O converter é inicializado uma única vez (singleton) para evitar
recarregar os modelos de layout a cada chamada.
"""

from pathlib import Path
from functools import lru_cache

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions


@lru_cache(maxsize=1)
def _get_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True  # PDFs digitais nativos não precisam de OCR (possivel ajustar para false)
    pipeline_options.do_table_structure = True  # Converte tabelas para Markdown

    return DocumentConverter(
        format_options={
            "pdf": PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrai texto de um PDF e retorna como Markdown estruturado.

    Usa Docling para análise de layout, preservando hierarquia de seções,
    tabelas e listas. PDFs digitais nativos são processados sem OCR.
    """
    converter = _get_converter()
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()
