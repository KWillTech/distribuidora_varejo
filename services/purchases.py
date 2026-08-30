"""Orquestra compra, recebimento, estoque e conta a pagar."""

from __future__ import annotations

from pathlib import Path
from datetime import date

from models.auth import AuthenticatedSession, Permission
from models.stock import StockMovementRequest, StockMovementType
from models.purchase import Purchase, PurchaseInput, PurchaseStatus
from repositories.auth import AuditRepository
from repositories.catalog import ProductRepository
from repositories.purchases import PurchaseRepository
from services.rbac import require_permission
from services.stock import StockService
from services.purchase_pdf import PurchaseOrderPdfService


class PurchaseService:
    def __init__(self, purchases: PurchaseRepository, products: ProductRepository, stock: StockService, audit: AuditRepository, pdf: PurchaseOrderPdfService | None = None) -> None:
        self._purchases = purchases; self._products = products; self._stock = stock; self._audit = audit; self._pdf = pdf or PurchaseOrderPdfService()

    def create_order(self, session: AuthenticatedSession, data: PurchaseInput, output_dir: Path | None = None) -> Purchase:
        """Registra e gera o pedido sem alterar estoque ou contas a pagar."""
        require_permission(session, Permission.PURCHASES_CREATE)
        purchase = self._purchases.create_pending(data, session.user)
        pdf_path = self._pdf.generate(purchase, output_dir)
        purchase = self._purchases.mark_sent(purchase.id or "", str(pdf_path))
        self._audit.record(user=session.user, action="pedido_compra_enviado", module="compras", affected_id=purchase.id, details={"numero": purchase.number, "fornecedor": purchase.supplier_name, "total": str(purchase.total), "pdf": str(pdf_path)})
        return purchase

    def confirm_receipt(self, session: AuthenticatedSession, purchase_id: str, invoice_numbers: list[str]) -> Purchase:
        require_permission(session, Permission.PURCHASES_CREATE)
        normalized = []
        seen = set()
        for number in invoice_numbers:
            clean = number.strip()
            if clean and clean.casefold() not in seen: normalized.append(clean); seen.add(clean.casefold())
        if not normalized: raise ValueError("Informe pelo menos um número de nota fiscal.")
        if any(len(number) > 100 for number in normalized): raise ValueError("Cada número de nota deve ter no máximo 100 caracteres.")
        purchase = self._purchases.get(purchase_id)
        if purchase is None or purchase.status not in (PurchaseStatus.PENDING, PurchaseStatus.SENT): raise ValueError("Somente pedido enviado pode ser recebido.")
        conflicts = self._purchases.invoice_conflicts(purchase.supplier_id, normalized, purchase_id)
        if conflicts:
            details = ", ".join(f"{invoice} (pedido {order})" for invoice, order in conflicts)
            raise ValueError(f"NF-e já vinculada a este fornecedor: {details}.")
        purchase = self._purchases.confirm_receipt(purchase_id, normalized)
        self._audit.record(user=session.user, action="recebimento_compra_confirmado", module="compras", affected_id=purchase.id, details={"numero": purchase.number, "notas": normalized})
        return purchase

    def invoice_entry_info(self, session: AuthenticatedSession, purchase_number: str) -> Purchase:
        require_permission(session, Permission.STOCK_VIEW)
        purchase = self._purchases.get_by_number(purchase_number)
        if purchase is None: raise ValueError("Pedido não encontrado.")
        if purchase.status != PurchaseStatus.RECEIPT_CONFIRMED: raise ValueError("O pedido ainda não teve o recebimento e as notas confirmados.")
        return purchase

    def post_invoice_entry(self, session: AuthenticatedSession, purchase_id: str, expiration_dates: dict[str, date]) -> Purchase:
        require_permission(session, Permission.STOCK_ADJUST)
        purchase = self._purchases.get(purchase_id)
        if purchase is None or purchase.status != PurchaseStatus.RECEIPT_CONFIRMED: raise ValueError("Pedido não está disponível para entrada de NF-e.")
        required = {item.product_id for item in purchase.items}
        if set(expiration_dates) != required: raise ValueError("Informe a data de validade de todos os produtos.")
        if any(value < date.today() for value in expiration_dates.values()): raise ValueError("A data de validade não pode estar vencida.")
        purchase = self._purchases.set_expiration_dates(purchase_id, expiration_dates)
        return self._receive_purchase(session, purchase, mark_failed=False)

    def receive(self, session: AuthenticatedSession, data: PurchaseInput) -> Purchase:
        """Compatibilidade: registra e recebe imediatamente."""
        require_permission(session, Permission.PURCHASES_CREATE)
        purchase = self._purchases.create_pending(data, session.user)
        return self._receive_purchase(session, purchase, mark_failed=True)

    def _receive_purchase(self, session: AuthenticatedSession, purchase: Purchase, *, mark_failed: bool) -> Purchase:
        applied = []; payable_created = False
        try:
            for item in purchase.items:
                lot_code = item.lot_code or (purchase.number if item.expiration_date else None)
                movement = StockMovementRequest(product_id=item.product_id, product_name=item.product_name, movement_type=StockMovementType.PURCHASE_ENTRY, package_type=item.package_type, informed_quantity=item.quantity, units_per_pack=item.units_per_pack, reason=f"Recebimento da compra {purchase.number}", related_document=purchase.invoice_number or purchase.number, lot_code=lot_code, expiration_date=item.expiration_date)
                self._stock.move(session, movement); applied.append(item)
            for item in purchase.items:
                self._products.update_unit_cost(item.product_id, item.unit_cost)
            self._purchases.create_payable(purchase); payable_created = purchase.due_date is not None or bool(purchase.installment_days)
            purchase = self._purchases.mark_received(purchase.id or "")
            self._audit.record(user=session.user, action="compra_recebida", module="compras", affected_id=purchase.id, details={"numero": purchase.number, "total": str(purchase.total), "itens": len(purchase.items)})
            return purchase
        except Exception:
            if payable_created: self._purchases.cancel_payable(purchase.id or "")
            for item in reversed(applied):
                compensation = StockMovementRequest(product_id=item.product_id, product_name=item.product_name, movement_type=StockMovementType.EXCHANGE_EXIT, package_type=item.package_type, informed_quantity=item.quantity, units_per_pack=item.units_per_pack, reason=f"Compensação da compra {purchase.number}", related_document=purchase.number, lot_code=item.lot_code or (purchase.number if item.expiration_date else None))
                try: self._stock.move(session, compensation)
                except Exception as compensation_error:
                    self._audit.record(user=session.user, action="falha_compensacao_compra", module="compras", affected_id=purchase.id, details={"produto_id": item.product_id, "erro": type(compensation_error).__name__})
            if mark_failed: self._purchases.mark_failed(purchase.id or "")
            raise

    def cancel(self, session: AuthenticatedSession, purchase_id: str, reason: str) -> Purchase:
        require_permission(session, Permission.PURCHASES_CANCEL)
        if len(reason.strip()) < 3: raise ValueError("Informe o motivo do cancelamento.")
        purchase = self._purchases.get(purchase_id)
        if purchase is None or purchase.status != PurchaseStatus.RECEIVED: raise ValueError("Somente compra recebida pode ser cancelada.")
        reversed_items = []
        try:
            for item in purchase.items:
                movement = StockMovementRequest(product_id=item.product_id, product_name=item.product_name, movement_type=StockMovementType.EXCHANGE_EXIT, package_type=item.package_type, informed_quantity=item.quantity, units_per_pack=item.units_per_pack, reason=f"Cancelamento da compra {purchase.number}: {reason}", related_document=purchase.invoice_number or purchase.number, lot_code=item.lot_code or (purchase.number if item.expiration_date else None))
                self._stock.move(session, movement); reversed_items.append(item)
            cancelled = self._purchases.cancel(purchase_id, reason)
            self._audit.record(user=session.user, action="compra_cancelada", module="compras", affected_id=purchase_id, reason=reason)
            return cancelled
        except Exception:
            for item in reversed(reversed_items):
                compensation = StockMovementRequest(product_id=item.product_id, product_name=item.product_name, movement_type=StockMovementType.RETURN_ENTRY, package_type=item.package_type, informed_quantity=item.quantity, units_per_pack=item.units_per_pack, reason=f"Compensação do cancelamento {purchase.number}", related_document=purchase.number, lot_code=item.lot_code or (purchase.number if item.expiration_date else None), expiration_date=item.expiration_date)
                try: self._stock.move(session, compensation)
                except Exception as compensation_error:
                    self._audit.record(user=session.user, action="falha_compensacao_cancelamento_compra", module="compras", affected_id=purchase.id, details={"produto_id": item.product_id, "erro": type(compensation_error).__name__})
            raise

    def list_page(self, session: AuthenticatedSession, **filters) -> tuple[list[Purchase], int]:
        require_permission(session, Permission.PURCHASES_CREATE); return self._purchases.list_page(**filters)
