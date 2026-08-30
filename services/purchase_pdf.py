"""Geração do PDF de pedido de compra."""
import re
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from models.catalog import PackageType
from models.purchase import Purchase, PurchasePaymentMethod

def _brl(value) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

class PurchaseOrderPdfService:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parents[1] / "reports" / "purchase_orders"

    @staticmethod
    def filename(purchase: Purchase) -> str:
        supplier = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", purchase.supplier_name).strip().rstrip(".")
        supplier = re.sub(r"\s+", " ", supplier) or "fornecedor"
        return f"pedido_{supplier}-{purchase.number}.pdf"

    def generate(self, purchase: Purchase, output_dir: Path | None = None) -> Path:
        destination = Path(output_dir) if output_dir else self.output_dir
        destination.mkdir(parents=True, exist_ok=True); path = (destination / self.filename(purchase)).resolve()
        styles = getSampleStyleSheet(); title = ParagraphStyle("TitleBrand", parent=styles["Title"], textColor=colors.HexColor("#D97706"), alignment=TA_CENTER, fontSize=20)
        right = ParagraphStyle("Right", parent=styles["Normal"], alignment=TA_RIGHT)
        document = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
        story = [Paragraph("ADEGA DO BRUNINHO", title), Paragraph("PEDIDO DE COMPRA", ParagraphStyle("Sub", parent=styles["Heading2"], alignment=TA_CENTER)), Spacer(1, 8)]
        story += [Table([["Pedido", purchase.number, "Data", purchase.created_at.astimezone().strftime("%d/%m/%Y %H:%M")], ["Fornecedor", purchase.supplier_name, "NF-e", purchase.invoice_number or "—"]], colWidths=[25*mm, 65*mm, 25*mm, 65*mm], style=TableStyle([("GRID",(0,0),(-1,-1),.4,colors.HexColor("#D97706")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#1C1C1C")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#1C1C1C")),("TEXTCOLOR",(0,0),(0,-1),colors.white),("TEXTCOLOR",(2,0),(2,-1),colors.white),("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("PADDING",(0,0),(-1,-1),6)])), Spacer(1, 12)]
        rows = [["Produto", "Tipo", "Qtd.", "Unidades", "Preço", "Total"]]
        for item in purchase.items: rows.append([item.product_name, "Fardo" if item.package_type == PackageType.PACK else "Unidade", str(item.quantity), str(item.converted_units), _brl(item.cost_per_package), _brl(item.total)])
        items = Table(rows, colWidths=[65*mm, 25*mm, 18*mm, 22*mm, 27*mm, 27*mm], repeatRows=1); items.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1C1C1C")),("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#FBBF24")),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#C4C4C4")),("ALIGN",(2,1),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),5)])); story += [items, Spacer(1, 12)]
        payment = {PurchasePaymentMethod.CASH:"Dinheiro", PurchasePaymentMethod.PIX:"Pix", PurchasePaymentMethod.BOLETO:"Boleto", PurchasePaymentMethod.CREDIT:"A prazo"}[purchase.payment_method]
        if purchase.payment_method == PurchasePaymentMethod.CREDIT: payment += " — " + "/".join(map(str, purchase.installment_days)) + " dias"
        elif purchase.due_date: payment += " — vencimento " + purchase.due_date.strftime("%d/%m/%Y")
        story += [Paragraph(f"<b>Pagamento:</b> {payment}", styles["Normal"])]
        if purchase.notes: story += [Paragraph(f"<b>Observações:</b> {purchase.notes}", styles["Normal"])]
        story += [Spacer(1, 10), Paragraph(f"<b>Total do pedido: {_brl(purchase.total)}</b>", right)]
        document.build(story); return path
