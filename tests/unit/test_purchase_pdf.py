"""Teste do documento de pedido enviado ao fornecedor."""
from decimal import Decimal
from models.catalog import PackageType
from models.purchase import Purchase, PurchaseItem, PurchasePaymentMethod, PurchaseStatus
from services.purchase_pdf import PurchaseOrderPdfService

def test_generates_purchase_order_pdf(tmp_path) -> None:
    purchase = Purchase(id="p1", number="CP-00000001", supplier_id="s1", supplier_name="Fornecedor Teste", supplier_whatsapp="11999999999", items=[PurchaseItem(product_id="x1", product_name="Cerveja", package_type=PackageType.PACK, quantity=2, units_per_pack=12, cost_per_package=Decimal("36.00"))], payment_method=PurchasePaymentMethod.CREDIT, installment_days=[7, 14, 21], status=PurchaseStatus.PENDING, created_by="admin")
    path = PurchaseOrderPdfService(tmp_path).generate(purchase)
    assert path.exists()
    assert path.name == "pedido_Fornecedor Teste-CP-00000001.pdf"
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1_000

def test_pdf_filename_removes_windows_invalid_characters() -> None:
    purchase = Purchase(id="p1", number="CP-2", supplier_id="s1", supplier_name='Bebidas: Silva/Filhos?', items=[PurchaseItem(product_id="x1", product_name="Água", package_type=PackageType.UNIT, quantity=1, cost_per_package=Decimal("2.00"))], payment_method=PurchasePaymentMethod.PIX, status=PurchaseStatus.PENDING, created_by="admin")
    assert PurchaseOrderPdfService.filename(purchase) == "pedido_Bebidas SilvaFilhos-CP-2.pdf"
