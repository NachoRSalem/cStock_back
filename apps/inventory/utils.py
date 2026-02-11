from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class RemitoPDFGenerator:
    def __init__(self, buffer, pedido):
        self.buffer = buffer
        self.pedido = pedido
        self.p = canvas.Canvas(self.buffer, pagesize=letter)
        self.width, self.height = letter

    def generar(self):
        self._escribir_cabecera()
        self._escribir_tabla_items()
        self.p.showPage()
        self.p.save()

    def _escribir_cabecera(self):
        self.p.setFont("Helvetica-Bold", 16)
        self.p.drawString(100, self.height - 50, f"REMITO DE PEDIDO #{self.pedido.id}")
        
        self.p.setFont("Helvetica", 12)
        self.p.drawString(100, self.height - 80, f"Destino: {self.pedido.destino.nombre}")
        self.p.drawString(100, self.height - 100, f"Fecha: {self.pedido.fecha_creacion.strftime('%d/%m/%Y')}")
        self.p.line(100, self.height - 110, 500, self.height - 110)

    def _escribir_tabla_items(self):
        y = self.height - 140
        self.p.setFont("Helvetica-Bold", 12)
        self.p.drawString(100, y, "Producto")
        self.p.drawString(400, y, "Cantidad")
        
        self.p.setFont("Helvetica", 11)
        for item in self.pedido.items.all():
            y -= 20
            self.p.drawString(100, y, item.producto.nombre)
            self.p.drawString(400, y, str(item.cantidad))