"""HTML-to-PDF conversion service.

POST /generate  {"html": "<h1>Hello</h1>"}
POST /invoice   {"company": "...", "items": [...], "total": 100}
Returns: PDF binary (application/pdf)
"""
import io
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

app = FastAPI(title="MicroVM PDF Generator")
templates = Environment(loader=FileSystemLoader("templates"))


class HtmlRequest(BaseModel):
    html: str
    filename: str = "document.pdf"


class InvoiceItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float


class InvoiceRequest(BaseModel):
    company: str
    recipient: str
    items: list[InvoiceItem]
    invoice_number: str = "INV-001"
    notes: str = ""


@app.post("/generate")
def generate_pdf(req: HtmlRequest):
    pdf = HTML(string=req.html).write_pdf()
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={req.filename}"},
    )


@app.post("/invoice")
def generate_invoice(req: InvoiceRequest):
    total = sum(i.quantity * i.unit_price for i in req.items)
    tmpl = templates.get_template("invoice.html")
    html = tmpl.render(
        company=req.company,
        recipient=req.recipient,
        items=req.items,
        invoice_number=req.invoice_number,
        total=total,
        notes=req.notes,
    )
    pdf = HTML(string=html).write_pdf()
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={req.invoice_number}.pdf"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "pdf-generator"}


@app.get("/")
def root():
    return {
        "service": "pdf-generator",
        "endpoints": {
            "/generate": "POST {html, filename} → PDF",
            "/invoice": "POST {company, recipient, items, invoice_number} → invoice PDF",
        },
    }
