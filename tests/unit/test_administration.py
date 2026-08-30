"""Validação segura de backups administrativos."""
import zipfile
import pytest
from services.administration import AdministrationService
class Repository:database=None
class Audit:pass
def test_invalid_backup_is_rejected(tmp_path):
    path=tmp_path/"invalid.zip"
    with zipfile.ZipFile(path,"w") as archive:archive.writestr("file.txt","invalid")
    with pytest.raises(ValueError,match="inválido"):AdministrationService(Repository(),Audit()).validate_backup(path)
def test_non_zip_backup_is_rejected(tmp_path):
    path=tmp_path/"invalid.zip"; path.write_text("not a zip",encoding="utf-8")
    with pytest.raises(ValueError,match="inválido"):AdministrationService(Repository(),Audit()).validate_backup(path)

def test_backup_collection_allowlist_excludes_unknown_collection():
    assert "usuarios" in AdministrationService.ALLOWED_COLLECTIONS
    assert "colecao_injetada" not in AdministrationService.ALLOWED_COLLECTIONS
