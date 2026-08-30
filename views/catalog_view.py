"""Tela de categorias e produtos com filtros e paginação."""

from math import ceil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from dialogs.catalog_dialogs import CategoryDialog
from dialogs.product_dialog import ProductDialog
from dialogs.pack_dialog import PackConfigurationDialog
from models.auth import AuthenticatedSession, Permission
from models.catalog import Category, Product
from services.catalog import CatalogService
from services.packaging import PackagingService
from views.dashboard_view import brl


class CatalogView(QWidget):
    def __init__(self, session: AuthenticatedSession, service: CatalogService, packaging_service: PackagingService, parent=None) -> None:
        super().__init__(parent); self.session = session; self.service = service; self.packaging_service = packaging_service; self.page = 1; self.total_pages = 1
        root = QVBoxLayout(self); title = QLabel("Categorias e produtos"); title.setObjectName("pageTitle"); root.addWidget(title); tabs = QTabWidget(); root.addWidget(tabs)
        products_page = QWidget(); products_layout = QVBoxLayout(products_page); filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Nome, código ou código de barras…"); self.search.setClearButtonEnabled(True); self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(350); self.search.textChanged.connect(self.timer.start); self.timer.timeout.connect(self._first)
        self.category_filter = QComboBox(); self.category_filter.currentIndexChanged.connect(self._first)
        self.status_filter = QComboBox(); self.status_filter.addItem("Ativos", True); self.status_filter.addItem("Inativos", False); self.status_filter.addItem("Todos", None); self.status_filter.currentIndexChanged.connect(self._first)
        self.low_stock = QCheckBox("Estoque baixo"); self.low_stock.toggled.connect(self._first)
        self.size = QComboBox(); self.size.addItems(["10", "20", "50", "100"]); self.size.setCurrentText("20"); self.size.currentIndexChanged.connect(self._first)
        new_product = QPushButton("Novo produto"); new_product.clicked.connect(self._create_product)
        if Permission.PRODUCTS_CREATE not in session.permissions: new_product.hide()
        for widget in (self.search, self.category_filter, self.status_filter, self.low_stock, self.size, new_product): filters.addWidget(widget)
        filters.setStretch(0, 1); products_layout.addLayout(filters)
        self.product_table = QTableWidget(0, 9); self.product_table.setHorizontalHeaderLabels(["Código", "Produto", "Categoria", "Fornecedor", "Preço un.", "Preço fardo", "Estoque mínimo", "Margem", "Status"]); self.product_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.product_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.product_table.setAlternatingRowColors(True); self.product_table.doubleClicked.connect(self._edit_product); products_layout.addWidget(self.product_table)
        self.product_table.setColumnHidden(7, Permission.PROFIT_VIEW not in session.permissions)
        product_actions = QHBoxLayout(); info_product = QPushButton("Exibir informações"); info_product.clicked.connect(self._show_product_info); configure_pack = QPushButton("Configurar fardo"); configure_pack.clicked.connect(self._configure_pack); edit_product = QPushButton("Editar"); edit_product.clicked.connect(self._edit_product); toggle = QPushButton("Ativar/Inativar"); toggle.clicked.connect(self._toggle_product)
        if Permission.PRODUCTS_EDIT not in session.permissions or Permission.PRODUCTS_CHANGE_PRICE not in session.permissions: configure_pack.hide()
        if Permission.PRODUCTS_EDIT not in session.permissions: edit_product.hide()
        if Permission.PRODUCTS_DEACTIVATE not in session.permissions: toggle.hide()
        product_actions.addWidget(info_product); product_actions.addWidget(configure_pack); product_actions.addWidget(edit_product); product_actions.addWidget(toggle); product_actions.addStretch(); self.previous = QPushButton("Anterior"); self.previous.clicked.connect(self._previous); self.page_label = QLabel(); self.next = QPushButton("Próxima"); self.next.clicked.connect(self._next); product_actions.addWidget(self.previous); product_actions.addWidget(self.page_label); product_actions.addWidget(self.next); products_layout.addLayout(product_actions); tabs.addTab(products_page, "Produtos")
        categories_page = QWidget(); categories_layout = QVBoxLayout(categories_page); self.category_table = QTableWidget(0, 3); self.category_table.setHorizontalHeaderLabels(["Categoria", "Descrição", "Status"]); self.category_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.category_table.doubleClicked.connect(self._edit_category); categories_layout.addWidget(self.category_table); category_actions = QHBoxLayout(); new_category = QPushButton("Nova categoria"); new_category.clicked.connect(self._create_category); edit_category = QPushButton("Editar categoria"); edit_category.clicked.connect(self._edit_category)
        if Permission.CATEGORIES_MANAGE not in session.permissions: new_category.hide(); edit_category.hide()
        category_actions.addWidget(new_category); category_actions.addWidget(edit_category); category_actions.addStretch(); categories_layout.addLayout(category_actions); tabs.addTab(categories_page, "Categorias")
        self.refresh_categories(); self.refresh_products()

    def refresh_categories(self) -> None:
        try: categories = self.service.list_categories(self.session, None)
        except PermissionError as exc: QMessageBox.warning(self, "Categorias", str(exc)); return
        current = self.category_filter.currentData(); self.category_filter.blockSignals(True); self.category_filter.clear(); self.category_filter.addItem("Todas as categorias", None)
        for category in categories:
            if category.active: self.category_filter.addItem(category.name, category.id)
        index = self.category_filter.findData(current); self.category_filter.setCurrentIndex(max(0, index)); self.category_filter.blockSignals(False)
        self.category_table.setRowCount(len(categories))
        for row, category in enumerate(categories):
            for column, value in enumerate((category.name, category.description or "—", "Ativa" if category.active else "Inativa")):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, category); self.category_table.setItem(row, column, item)
        self.category_table.resizeColumnsToContents()

    def refresh_products(self) -> None:
        try: result = self.service.list_products(self.session, search=self.search.text(), category_id=self.category_filter.currentData(), active=self.status_filter.currentData(), low_stock=self.low_stock.isChecked(), page=self.page, page_size=int(self.size.currentText()))
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Produtos", str(exc)); return
        self.total_pages = max(1, ceil(result.total / result.page_size)); self.product_table.setRowCount(len(result.items))
        for row, product in enumerate(result.items):
            values = (product.internal_code, product.name, product.category_name, product.main_supplier_name or "—", brl(product.unit_price), brl(product.pack_price) if product.pack_price is not None else "—", f"{product.minimum_stock} un.", f"{product.unit_margin_percent}%", "Ativo" if product.active else "Inativo")
            for column, value in enumerate(values): item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, product); self.product_table.setItem(row, column, item)
        self.product_table.resizeColumnsToContents(); self.page_label.setText(f"Página {self.page} de {self.total_pages} • {result.total} produto(s)"); self.previous.setEnabled(self.page > 1); self.next.setEnabled(self.page < self.total_pages)

    def _first(self, *_args) -> None: self.page = 1; self.refresh_products()
    def _selected_product(self) -> Product | None:
        row = self.product_table.currentRow()
        if row < 0: QMessageBox.information(self, "Seleção", "Selecione um produto."); return None
        return self.product_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    def _product_dialog(self, product: Product | None = None) -> ProductDialog | None:
        try: categories = self.service.list_categories(self.session, True); suppliers = self.service.supplier_options(self.session)
        except PermissionError as exc: QMessageBox.warning(self, "Produto", str(exc)); return None
        if not categories: QMessageBox.warning(self, "Produto", "Cadastre ao menos uma categoria ativa."); return None
        return ProductDialog(categories, suppliers, product, self)
    def _create_product(self) -> None:
        dialog = self._product_dialog()
        if not dialog or dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.create_product(self.session, data); self._first()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Cadastro não realizado", str(exc))
    def _edit_product(self, *_args) -> None:
        selected = self._selected_product()
        if not selected: return
        try: product = self.service.get_product(self.session, selected.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Produto", str(exc)); return
        dialog = self._product_dialog(product)
        if not dialog or dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.update_product(self.session, product.id or "", data); self.refresh_products()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Alteração não realizada", str(exc))
    def _toggle_product(self) -> None:
        product = self._selected_product()
        if not product: return
        reason, accepted = QInputDialog.getText(self, "Motivo", "Informe o motivo:")
        if not accepted: return
        try: self.service.set_product_active(self.session, product.id or "", not product.active, reason); self.refresh_products()
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Operação não realizada", str(exc))
    def _show_product_info(self) -> None:
        selected = self._selected_product()
        if not selected: return
        try: product = self.service.get_product(self.session, selected.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Produto", str(exc)); return
        lines = [
            f"Código interno: {product.internal_code}", f"Produto: {product.name}",
            f"Categoria: {product.category_name}",
            f"Volume: {product.volume or '—'}", f"Unidade de medida: {product.measurement_unit}",
            f"Embalagem: {product.package_description or '—'}",
            f"Código de barras da unidade: {product.unit_barcode or '—'}",
            f"Código de barras do fardo: {product.pack_barcode or '—'}",
            f"Unidades por fardo: {product.units_per_pack or 'Produto sem fardo'}",
            f"Preço da unidade: {brl(product.unit_price)}",
            f"Preço do fardo: {brl(product.pack_price) if product.pack_price is not None else '—'}",
            f"Promoção unidade: {brl(product.promotional_unit_price) if product.promotional_unit_price is not None else '—'}",
            f"Promoção fardo: {brl(product.promotional_pack_price) if product.promotional_pack_price is not None else '—'}",
            f"Estoque: {product.stock_display}", f"Estoque mínimo: {product.minimum_stock} un.",
            f"Estoque máximo: {product.maximum_stock if product.maximum_stock is not None else '—'}",
            f"Localização: {product.storage_location or '—'}",
            f"Fornecedor principal: {product.main_supplier_name or '—'}",
            f"Lote inicial: {product.initial_lot or '—'}",
            f"Validade: {product.expiration_date.strftime('%d/%m/%Y') if product.expiration_date else '—'}",
            f"Foto: {product.photo_path or '—'}", f"Status: {'Ativo' if product.active else 'Inativo'}",
            f"Descrição: {product.description or '—'}",
        ]
        if Permission.COST_VIEW in self.session.permissions:
            lines.insert(12, f"Custo da unidade: {brl(product.unit_cost)}")
            lines.insert(13, f"Custo do fardo: {brl(product.calculated_pack_cost) if product.calculated_pack_cost is not None else '—'}")
        if Permission.PROFIT_VIEW in self.session.permissions:
            lines.insert(14, f"Margem da unidade: {product.unit_margin_percent}%")
        QMessageBox.information(self, f"Informações — {product.name}", "\n".join(lines))
    def _configure_pack(self) -> None:
        selected = self._selected_product()
        if not selected: return
        try: product = self.service.get_product(self.session, selected.id or "")
        except (ValueError, PermissionError) as exc: QMessageBox.warning(self, "Fardo", str(exc)); return
        dialog = PackConfigurationDialog(product, self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.packaging_service.configure_pack(self.session, product.id or "", data); self.refresh_products()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Configuração não realizada", str(exc))
    def _selected_category(self) -> Category | None:
        row = self.category_table.currentRow()
        if row < 0: QMessageBox.information(self, "Seleção", "Selecione uma categoria."); return None
        return self.category_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    def _create_category(self) -> None:
        dialog = CategoryDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.create_category(self.session, data); self.refresh_categories()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Categoria", str(exc))
    def _edit_category(self, *_args) -> None:
        category = self._selected_category()
        if not category: return
        dialog = CategoryDialog(category, self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            data = dialog.data()
            if data: self.service.update_category(self.session, category.id or "", data); self.refresh_categories(); self.refresh_products()
        except (ValueError, RuntimeError, PermissionError) as exc: QMessageBox.warning(self, "Categoria", str(exc))
    def _previous(self) -> None: self.page -= 1; self.refresh_products()
    def _next(self) -> None: self.page += 1; self.refresh_products()
