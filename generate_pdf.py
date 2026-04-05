from markdown_pdf import MarkdownPdf, Section

md_file = "legacy/docs/QuantumTutor_v1.2_Especificacion.md"
pdf_file = "legacy/docs/QuantumTutor_v1.2_Especificacion.pdf"

with open(md_file, "r", encoding="utf-8") as f:
    text = f.read()

pdf = MarkdownPdf(toc_level=2)
pdf.add_section(Section(text))
pdf.save(pdf_file)
print(f"PDF generado exitosamente en: {pdf_file}")
