"""Teste dos campos rápidos do PDV."""
from decimal import Decimal
from models.auth import AuthenticatedSession,Permission,ProfileCode,User
from models.catalog import PackageType,Product
from views.pos_view import PosView

class Catalog:
    def pos_products(self,session):
        return [Product(id="p1",internal_code="CER-1",unit_barcode="12345678",pack_barcode="87654321",name="Cerveja",category_id="c1",category_name="Cervejas",units_per_pack=12,unit_price=Decimal("5"),pack_price=Decimal("50"))]
class Sales: pass

def session():
    user=User(id="u1",username="caixa",email="caixa@example.com",full_name="Pessoa Caixa",profile_code=ProfileCode.CASHIER)
    return AuthenticatedSession(session_id="s1",user=user,permissions={Permission.POS_ACCESS})

def test_barcode_fills_product_and_package(qtbot):
    view=PosView(session(),Catalog(),Sales()); qtbot.addWidget(view)
    view.barcode.setText("87654321"); view._barcode_entered()
    assert view.product.text()=="Cerveja"
    assert view.package.currentData()==PackageType.PACK
    view.quantity.setValue(2); view._add()
    assert view.items[0].converted_units==24
    assert view.barcode.text()==""

def test_product_can_be_typed(qtbot):
    view=PosView(session(),Catalog(),Sales()); qtbot.addWidget(view)
    view.product.setText("cerveja")
    view.quantity.setValue(3); view._add()
    assert view.items[0].product_name=="Cerveja"
    assert view.items[0].converted_units==3
