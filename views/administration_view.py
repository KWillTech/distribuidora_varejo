"""Tela administrativa de auditoria, configurações e backup."""
from datetime import date,timedelta
from pathlib import Path
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox,QDateEdit,QFileDialog,QFormLayout,QHBoxLayout,QInputDialog,QLabel,QLineEdit,QMessageBox,QPushButton,QSpinBox,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from models.auth import Permission
class AdministrationView(QWidget):
    def __init__(self,session,service,parent=None):
        super().__init__(parent); self.session=session; self.service=service; root=QVBoxLayout(self); title=QLabel("Administração do sistema"); title.setObjectName("pageTitle"); root.addWidget(title); tabs=QTabWidget(); root.addWidget(tabs)
        if Permission.AUDIT_VIEW in session.permissions:tabs.addTab(self._audit_tab(),"Auditoria")
        if Permission.SETTINGS_MANAGE in session.permissions:tabs.addTab(self._settings_tab(),"Configurações")
        if {Permission.BACKUP_CREATE,Permission.BACKUP_RESTORE}&session.permissions:tabs.addTab(self._backup_tab(),"Backup")
    def _audit_tab(self):
        page=QWidget(); root=QVBoxLayout(page); filters=QHBoxLayout(); today=date.today(); self.audit_start=QDateEdit(QDate(today.year,today.month,1)); self.audit_end=QDateEdit(QDate.currentDate()); self.audit_search=QLineEdit(); self.audit_search.setPlaceholderText("Usuário, ação ou motivo...")
        for d in (self.audit_start,self.audit_end):d.setCalendarPopup(True); d.setDisplayFormat("dd/MM/yyyy")
        button=QPushButton("Pesquisar"); button.clicked.connect(self._load_audit)
        for w in (QLabel("De"),self.audit_start,QLabel("Até"),self.audit_end,self.audit_search,button):filters.addWidget(w)
        root.addLayout(filters); self.audit_table=QTableWidget(0,7); self.audit_table.setHorizontalHeaderLabels(["Data","Usuário","Perfil","Módulo","Ação","Registro","Motivo"]); root.addWidget(self.audit_table); self._load_audit(); return page
    def _load_audit(self):
        try:rows=self.service.audit_list(self.session,self.audit_start.date().toPython(),self.audit_end.date().toPython(),search=self.audit_search.text())
        except Exception as exc:QMessageBox.warning(self,"Auditoria",str(exc)); return
        self.audit_table.setRowCount(len(rows))
        for row,d in enumerate(rows):
            values=(d.get("data_hora").strftime("%d/%m/%Y %H:%M:%S"),d.get("usuario",""),d.get("perfil",""),d.get("modulo",""),d.get("acao",""),d.get("registro_afetado") or "—",d.get("motivo") or "—")
            for col,value in enumerate(values):self.audit_table.setItem(row,col,QTableWidgetItem(str(value)))
        self.audit_table.resizeColumnsToContents()
    def _settings_tab(self):
        page=QWidget(); root=QVBoxLayout(page); form=QFormLayout(); self.company=QLineEdit(); self.alert_days=QSpinBox(); self.alert_days.setRange(1,365); self.auto_backup=QCheckBox("Habilitar backup automático"); self.backup_folder=QLineEdit(); choose=QPushButton("Escolher pasta"); choose.clicked.connect(self._choose_folder); folder=QHBoxLayout(); folder.addWidget(self.backup_folder); folder.addWidget(choose)
        form.addRow("Nome da empresa",self.company); form.addRow("Alerta de validade (dias)",self.alert_days); form.addRow("Backup",self.auto_backup); form.addRow("Diretório do backup",folder); root.addLayout(form); save=QPushButton("Salvar configurações"); save.clicked.connect(self._save_settings); root.addWidget(save); root.addStretch(); self._load_settings(); return page
    def _load_settings(self):
        values=self.service.get_settings(self.session); self.company.setText(str(values.get("app.empresa_nome","Adega do Bruninho"))); self.alert_days.setValue(int(values.get("app.estoque_alerta_dias",30))); self.auto_backup.setChecked(bool(values.get("app.backup_automatico",False))); self.backup_folder.setText(str(values.get("app.backup_diretorio","backups")))
    def _choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Diretório de backups",self.backup_folder.text())
        if folder:self.backup_folder.setText(folder)
    def _save_settings(self):
        try:self.service.save_settings(self.session,{"app.empresa_nome":self.company.text(),"app.estoque_alerta_dias":self.alert_days.value(),"app.backup_automatico":self.auto_backup.isChecked(),"app.backup_diretorio":self.backup_folder.text()}); QMessageBox.information(self,"Configurações","Configurações salvas.")
        except Exception as exc:QMessageBox.warning(self,"Configurações",str(exc))
    def _backup_tab(self):
        page=QWidget(); root=QVBoxLayout(page); info=QLabel("O backup inclui todas as coleções, manifesto e checksum de integridade."); info.setWordWrap(True); root.addWidget(info)
        if Permission.BACKUP_CREATE in self.session.permissions:create=QPushButton("Criar backup manual"); create.clicked.connect(self._create_backup); root.addWidget(create)
        if Permission.BACKUP_RESTORE in self.session.permissions:restore=QPushButton("Restaurar backup"); restore.clicked.connect(self._restore_backup); root.addWidget(restore)
        root.addStretch(); return page
    def _create_backup(self):
        path,_=QFileDialog.getSaveFileName(self,"Salvar backup",f"backup_adega_{date.today():%Y%m%d}.zip","Backup ZIP (*.zip)")
        if path:
            try:self.service.create_backup(self.session,path); QMessageBox.information(self,"Backup","Backup criado e validado com sucesso.")
            except Exception as exc:QMessageBox.warning(self,"Backup",str(exc))
    def _restore_backup(self):
        path,_=QFileDialog.getOpenFileName(self,"Selecionar backup","","Backup ZIP (*.zip)")
        if not path:return
        confirmation,ok=QInputDialog.getText(self,"Restaurar backup","Esta operação substituirá os dados atuais.\nDigite RESTAURAR para confirmar:")
        if not ok:return
        try:self.service.restore_backup(self.session,path,confirmation); QMessageBox.information(self,"Restauração concluída","Backup restaurado. Reinicie o sistema para recarregar os dados.")
        except Exception as exc:QMessageBox.warning(self,"Restauração não realizada",str(exc))
