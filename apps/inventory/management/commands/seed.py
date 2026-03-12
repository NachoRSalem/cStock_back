"""
Comando de seed para poblar la base de datos con datos de prueba.
Uso: python manage.py seed
"""

import random
from decimal import Decimal
from datetime import timedelta, date
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Limpia la base de datos y la puebla con datos de prueba realistas."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("⚠️  Limpiando datos existentes..."))
        self._clear_data()

        self.stdout.write("📍 Creando ubicaciones y sub-ubicaciones...")
        ubicaciones, sub_ubicaciones_map = self._create_locations()

        self.stdout.write("👤 Creando usuarios...")
        users_map = self._create_users(ubicaciones)

        self.stdout.write("📦 Creando categorías y productos...")
        productos = self._create_products()

        self.stdout.write("🗃️  Creando stock inicial...")
        self._create_stock(ubicaciones, sub_ubicaciones_map, productos)

        self.stdout.write("🛒 Creando pedidos...")
        self._create_pedidos(ubicaciones, sub_ubicaciones_map, productos, users_map)

        self.stdout.write("💰 Creando ventas...")
        self._create_ventas(ubicaciones, sub_ubicaciones_map, productos, users_map)

        self.stdout.write(self.style.SUCCESS("\n✅ Seed completado exitosamente!"))
        self._print_summary(users_map)

    # ─────────────────────────────────────────────────────────────────────────
    # CLEAR
    # ─────────────────────────────────────────────────────────────────────────

    def _clear_data(self):
        from apps.sales.models import VentaItem, Venta
        from apps.inventory.models import PedidoItem, Pedido, Stock
        from apps.locations.models import SubUbicacion, Ubicacion
        from apps.products.models import Producto, Categoria

        VentaItem.objects.all().delete()
        Venta.objects.all().delete()
        PedidoItem.objects.all().delete()
        Pedido.objects.all().delete()
        Stock.objects.all().delete()
        SubUbicacion.objects.all().delete()
        Ubicacion.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        User.objects.filter(username="admin").delete()
        Producto.objects.all().delete()
        Categoria.objects.all().delete()
        self.stdout.write("   ✓ Datos anteriores eliminados.")

    # ─────────────────────────────────────────────────────────────────────────
    # LOCATIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _create_locations(self):
        from apps.locations.models import Ubicacion, SubUbicacion

        ubicaciones_def = [
            ("Kiosco Campo",     "sucursal"),
            ("Kiosco Centro",    "sucursal"),
            ("Comedor Campo",    "sucursal"),
            ("Comedor Centro",   "sucursal"),
            ("Hidrocinetic",     "sucursal"),
            ("Almacen el dique", "almacen"),
        ]

        ubicaciones = {}
        sub_ubicaciones_map = {}

        for nombre, tipo in ubicaciones_def:
            ub = Ubicacion.objects.create(nombre=nombre, tipo=tipo)
            ubicaciones[nombre] = ub

            subs = []
            sub_defs = [
                ("Góndola Principal", "ambiente"),
                ("Estantería Varios", "ambiente"),
                ("Freezer Central",   "freezer"),
                ("Heladera 1",        "heladera"),
            ]
            for sub_nombre, sub_tipo in sub_defs:
                sub = SubUbicacion.objects.create(
                    ubicacion=ub,
                    nombre=sub_nombre,
                    tipo=sub_tipo,
                )
                subs.append(sub)

            sub_ubicaciones_map[nombre] = {
                "ambiente": [s for s in subs if s.tipo == "ambiente"],
                "freezer":  [s for s in subs if s.tipo == "freezer"],
                "heladera": [s for s in subs if s.tipo == "heladera"],
                "all":      subs,
            }
            self.stdout.write(f"   ✓ {nombre} ({tipo}) — 4 sub-ubicaciones")

        return ubicaciones, sub_ubicaciones_map

    # ─────────────────────────────────────────────────────────────────────────
    # USERS
    # ─────────────────────────────────────────────────────────────────────────

    def _create_users(self, ubicaciones):
        admin = User.objects.create_superuser(
            username="admin",
            password="admin1234",
            email="admin@eldique.com",
            first_name="Administrador",
            last_name="Sistema",
            rol="admin",
        )
        self.stdout.write("   ✓ admin / admin1234  (rol: admin)")

        users_map = {"admin": admin}

        sucursal_users = [
            ("KioscoCampo",    "Kiosco Campo"),
            ("KioscoCentro",   "Kiosco Centro"),
            ("ComedorCampo",   "Comedor Campo"),
            ("ComedorCentro",  "Comedor Centro"),
            ("Hidrocinetic",   "Hidrocinetic"),
        ]

        for username, sucursal_nombre in sucursal_users:
            password = f"{username}1234"
            ub = ubicaciones[sucursal_nombre]
            u = User.objects.create_user(
                username=username,
                password=password,
                email=f"{username.lower()}@eldique.com",
                first_name=username,
                rol="sucursal",
                sucursal_asignada=ub,
            )
            users_map[sucursal_nombre] = u
            self.stdout.write(f"   ✓ {username} / {password}  → {sucursal_nombre}")

        return users_map

    # ─────────────────────────────────────────────────────────────────────────
    # PRODUCTS
    # ─────────────────────────────────────────────────────────────────────────

    def _create_products(self):
        from apps.products.models import Categoria, Producto

        cats = {}
        for nombre in ["Bebidas", "Golosinas", "Lácteos y Fiambres", "Snacks", "Galletitas", "Conservas", "Congelados", "Limpieza"]:
            cats[nombre] = Categoria.objects.create(nombre=nombre)

        productos_def = [
            # nombre                               categoria              conservacion  precio  costo   sku      dias_caducidad
            # Bebidas - Caducidad larga (180 días = 6 meses)
            ("Coca-Cola 500ml",                   "Bebidas",             "ambiente",   1200,   800,   "BEB001",  180),
            ("Pepsi 500ml",                       "Bebidas",             "ambiente",   1100,   740,   "BEB002",  180),
            ("Sprite 500ml",                      "Bebidas",             "ambiente",   1100,   740,   "BEB003",  180),
            ("Fanta Naranja 500ml",               "Bebidas",             "ambiente",   1100,   740,   "BEB004",  180),
            ("Agua Mineral Villavicencio 500ml",  "Bebidas",             "ambiente",    500,   310,   "BEB005",  365),  # Agua dura más
            ("Gatorade Naranja 500ml",            "Bebidas",             "ambiente",   1400,   950,   "BEB006",  180),
            ("Jugo Cepita Naranja 200ml",         "Bebidas",             "heladera",    600,   380,   "BEB007",  60),   # Jugos refrigerados duran menos
            # Lácteos y Fiambres - Caducidad corta (15-30 días)
            ("Leche La Serenísima Entera 1L",     "Lácteos y Fiambres",  "heladera",   1300,   950,   "LAC001",  15),
            ("Yogur Danone Frutilla 200g",        "Lácteos y Fiambres",  "heladera",    700,   450,   "LAC002",  20),
            ("Queso Cremoso por 200g",            "Lácteos y Fiambres",  "heladera",   2500,  1800,   "LAC003",  30),
            ("Jamón Cocido por 200g",             "Lácteos y Fiambres",  "heladera",   2200,  1600,   "LAC004",  10),   # Fiambres frescos duran poco
            # Golosinas - Caducidad media a larga (90-365 días)
            ("Alfajor Oreo",                      "Golosinas",           "ambiente",    800,   550,   "GOL001",  120),
            ("Alfajor Milka",                     "Golosinas",           "ambiente",    900,   610,   "GOL002",  120),
            ("Chocolate Blanco Cofler 55g",       "Golosinas",           "ambiente",    600,   360,   "GOL003",  90),
            ("Caramelos Halls Sin Azúcar",        "Golosinas",           "ambiente",    500,   300,   "GOL004",  365),  # Caramelos duran mucho
            ("Chicle Beldent Menta x10",          "Golosinas",           "ambiente",    400,   250,   "GOL005",  365),
            ("Chupetín Pops",                     "Golosinas",           "ambiente",    200,   110,   "GOL006",  365),
            # Snacks - Caducidad media (60-90 días)
            ("Palitos de Queso Pehuamar 70g",     "Snacks",              "ambiente",    900,   600,   "SNA001",  60),
            ("Papas Fritas Lay's Classic 70g",    "Snacks",              "ambiente",   1000,   700,   "SNA002",  90),
            ("Maní con Sal Pehuamar 100g",        "Snacks",              "ambiente",    800,   500,   "SNA003",  90),
            # Galletitas - Caducidad media (90-120 días)
            ("Galletitas Oreo x8",                "Galletitas",          "ambiente",    700,   450,   "GAL001",  120),
            ("Galletitas Toddy x16",              "Galletitas",          "ambiente",    600,   400,   "GAL002",  120),
            ("Galletitas Crackers Terrabusi",     "Galletitas",          "ambiente",    500,   320,   "GAL003",  90),
            ("Galletitas de Limón Granix",        "Galletitas",          "ambiente",    650,   430,   "GAL004",  90),
            # Conservas - SIN caducidad (productos estables)
            ("Atún al Natural La Campagnola",     "Conservas",           "ambiente",   1400,   950,   "CON001",  None),  # Sin vencimiento
            ("Tomate Triturado Arcor 400g",       "Conservas",           "ambiente",    900,   580,   "CON002",  None),
            ("Mayonesa Hellmann's 250g",          "Conservas",           "ambiente",   1800,  1200,   "CON003",  None),
            # Congelados - Caducidad larga (180 días)
            ("Helado Palito Bon o Bon",           "Congelados",          "freezer",     800,   490,   "CON004",  180),
            ("Empanadas Congeladas La Salteña x12","Congelados",         "freezer",    2800,  2000,   "CON005",  180),
            # Limpieza - SIN caducidad
            ("Limpol Cloro 500ml",                "Limpieza",            "ambiente",    900,   580,   "LIM001",  None),
        ]

        productos = []
        for nombre, cat_nombre, conservacion, precio, costo, sku, dias_caducidad in productos_def:
            p = Producto.objects.create(
                nombre=nombre,
                categoria=cats[cat_nombre],
                tipo_conservacion=conservacion,
                precio_venta=Decimal(str(precio)),
                costo_compra=Decimal(str(costo)),
                sku=sku,
                dias_caducidad=dias_caducidad,
            )
            productos.append(p)

        self.stdout.write(f"   ✓ {len(productos)} productos en {len(cats)} categorías")
        return productos

    # ─────────────────────────────────────────────────────────────────────────
    # STOCK INICIAL
    # ─────────────────────────────────────────────────────────────────────────

    def _create_stock(self, ubicaciones, sub_ubicaciones_map, productos):
        from apps.inventory.models import Stock

        total = 0
        hoy = date.today()
        
        # Categorizar productos por días de caducidad
        prods_sin_vencimiento = [p for p in productos if p.dias_caducidad is None]
        prods_con_vencimiento = [p for p in productos if p.dias_caducidad is not None]
        
        for nombre, ub in ubicaciones.items():
            subs = sub_ubicaciones_map[nombre]
            
            # Productos SIN vencimiento (conservas, limpieza, etc.)
            for prod in prods_sin_vencimiento:
                if prod.tipo_conservacion == "freezer":
                    sub_list = subs["freezer"]
                elif prod.tipo_conservacion == "heladera":
                    sub_list = subs["heladera"]
                else:
                    sub_list = subs["ambiente"]

                sub = random.choice(sub_list)
                cantidad = random.randint(8, 50)
                Stock.objects.create(
                    producto=prod,
                    sub_ubicacion=sub,
                    cantidad=cantidad,
                    # Sin fecha_ingreso ni lote para productos sin caducidad
                )
                total += 1
            
            # Productos CON vencimiento - crear múltiples lotes con diferentes estados
            for prod in prods_con_vencimiento:
                if prod.tipo_conservacion == "freezer":
                    sub_list = subs["freezer"]
                elif prod.tipo_conservacion == "heladera":
                    sub_list = subs["heladera"]
                else:
                    sub_list = subs["ambiente"]

                sub = random.choice(sub_list)
                dias_caducidad = prod.dias_caducidad
                
                # Crear 1-3 lotes diferentes por producto/ubicación
                num_lotes = random.randint(1, 3)
                
                for i in range(num_lotes):
                    # Decidir el estado del lote
                    estado = random.choice([
                        "vigente",      # 40% - Stock reciente
                        "vigente",
                        "por_vencer",   # 30% - Cerca del vencimiento
                        "por_vencer",
                        "vencido",      # 30% - Ya vencido
                    ])
                    
                    if estado == "vigente":
                        # Producto reciente: ingresó hace 0-30% de su vida útil
                        dias_desde_ingreso = random.randint(0, int(dias_caducidad * 0.3))
                    elif estado == "por_vencer":
                        # Por vencer: ingresó hace 70-95% de su vida útil
                        dias_desde_ingreso = random.randint(int(dias_caducidad * 0.7), int(dias_caducidad * 0.95))
                    else:  # vencido
                        # Vencido: ingresó hace más del 100% de su vida útil
                        dias_desde_ingreso = random.randint(dias_caducidad + 1, dias_caducidad + 30)
                    
                    fecha_ingreso = hoy - timedelta(days=dias_desde_ingreso)
                    lote = f"LOTE-{prod.sku}-{fecha_ingreso.strftime('%Y%m%d')}-{i+1}"
                    cantidad = random.randint(5, 30)
                    
                    Stock.objects.create(
                        producto=prod,
                        sub_ubicacion=sub,
                        cantidad=cantidad,
                        fecha_ingreso=fecha_ingreso,
                        lote=lote,
                    )
                    total += 1

        self.stdout.write(f"   ✓ {total} registros de stock creados (incluyendo lotes con diferentes vencimientos)")

    # ─────────────────────────────────────────────────────────────────────────
    # PEDIDOS
    # ─────────────────────────────────────────────────────────────────────────

    def _create_pedidos(self, ubicaciones, sub_ubicaciones_map, productos, users_map):
        from apps.inventory.models import Pedido, PedidoItem

        sucursales_nombres = [n for n in ubicaciones if ubicaciones[n].tipo == "sucursal"]
        admin = users_map["admin"]
        almacen_ub = ubicaciones["Almacen el dique"]
        almacen_subs = sub_ubicaciones_map["Almacen el dique"]

        # Cada sucursal tiene 5 pedidos con estados variados
        estados_secuencia = ["recibido", "recibido", "aprobado", "rechazado", "pendiente"]
        total = 0

        for suc_nombre in sucursales_nombres:
            ub = ubicaciones[suc_nombre]
            user = users_map[suc_nombre]
            subs = sub_ubicaciones_map[suc_nombre]

            for i, estado in enumerate(estados_secuencia):
                productos_pedido = random.sample(productos, random.randint(3, 6))
                dias_atras = random.randint(1, 30)
                fecha = timezone.now() - timedelta(days=dias_atras)

                # Decidir si proviene del almacén o distribuidor
                proviene_de_almacen = estado in ("recibido", "aprobado") and random.choice([True, False])
                
                pedido = Pedido(
                    creado_por=user,
                    destino=ub,
                    estado=estado,
                    origen_tipo="sucursal" if proviene_de_almacen else "distribuidor",
                    origen_sucursal=almacen_ub if proviene_de_almacen else None,
                )
                # Forzar la fecha sobreescribiendo auto_now_add
                pedido.save()
                Pedido.objects.filter(pk=pedido.pk).update(fecha_creacion=fecha)

                for prod in productos_pedido:
                    cantidad = random.randint(5, 20)

                    # sub_ubicacion_destino sólo en pedidos recibidos
                    if estado == "recibido":
                        if prod.tipo_conservacion == "freezer":
                            sub_dest = random.choice(subs["freezer"])
                        elif prod.tipo_conservacion == "heladera":
                            sub_dest = random.choice(subs["heladera"])
                        else:
                            sub_dest = random.choice(subs["ambiente"])
                    else:
                        sub_dest = None

                    # sub_ubicacion_origen sólo si viene del almacén
                    if proviene_de_almacen and estado in ("recibido", "aprobado"):
                        if prod.tipo_conservacion == "freezer":
                            sub_orig = random.choice(almacen_subs["freezer"])
                        elif prod.tipo_conservacion == "heladera":
                            sub_orig = random.choice(almacen_subs["heladera"])
                        else:
                            sub_orig = random.choice(almacen_subs["ambiente"])
                    else:
                        sub_orig = None

                    PedidoItem.objects.create(
                        pedido=pedido,
                        producto=prod,
                        cantidad=cantidad,
                        precio_costo_momento=prod.costo_compra,
                        sub_ubicacion_destino=sub_dest,
                        sub_ubicacion_origen=sub_orig,
                    )

                total += 1

        self.stdout.write(f"   ✓ {total} pedidos creados ({len(sucursales_nombres)} sucursales × 5 estados)")

    # ─────────────────────────────────────────────────────────────────────────
    # VENTAS
    # ─────────────────────────────────────────────────────────────────────────

    def _create_ventas(self, ubicaciones, sub_ubicaciones_map, productos, users_map):
        from apps.sales.models import Venta, VentaItem
        from apps.inventory.models import Stock

        sucursales_nombres = [n for n in ubicaciones if ubicaciones[n].tipo == "sucursal"]
        total_ventas = 0
        total_items = 0

        for suc_nombre in sucursales_nombres:
            ub = ubicaciones[suc_nombre]
            user = users_map[suc_nombre]
            subs = sub_ubicaciones_map[suc_nombre]
            all_subs = subs["all"]

            for _ in range(10):
                dias_atras = random.randint(0, 20)
                fecha = timezone.now() - timedelta(days=dias_atras, hours=random.randint(0, 8))

                venta = Venta.objects.create(
                    vendedor=user,
                    sucursal=ub,
                    total=Decimal("0"),
                )
                # Forzar la fecha
                Venta.objects.filter(pk=venta.pk).update(fecha=fecha)

                # 2-4 productos por venta
                prods_venta = random.sample(productos, random.randint(2, 4))
                total_venta = Decimal("0")

                for prod in prods_venta:
                    # Elegir sub-ubicación correcta según conservación
                    if prod.tipo_conservacion == "freezer":
                        sub = random.choice(subs["freezer"])
                    elif prod.tipo_conservacion == "heladera":
                        sub = random.choice(subs["heladera"])
                    else:
                        sub = random.choice(subs["ambiente"])

                    cantidad = random.randint(1, 4)

                    # Buscar stock disponible para este producto/sub-ubicación
                    # Si hay múltiples lotes, tomar el más antiguo (FIFO)
                    stock_objs = Stock.objects.filter(
                        producto=prod,
                        sub_ubicacion=sub,
                    ).order_by('fecha_ingreso')
                    
                    stock_obj = None
                    if stock_objs.exists():
                        # Tomar el primer lote disponible
                        stock_obj = stock_objs.first()
                    else:
                        # Crear stock sin lote si no existe
                        stock_obj = Stock.objects.create(
                            producto=prod,
                            sub_ubicacion=sub,
                            cantidad=0,
                        )
                    
                    # Asegurar stock suficiente para vender
                    if stock_obj.cantidad < cantidad:
                        stock_obj.cantidad = cantidad + 10
                        stock_obj.save()

                    # Descontar stock
                    Stock.objects.filter(pk=stock_obj.pk).update(
                        cantidad=stock_obj.cantidad - cantidad
                    )

                    precio = prod.precio_venta
                    VentaItem.objects.create(
                        venta=venta,
                        producto=prod,
                        sub_ubicacion_origen=sub,
                        cantidad=cantidad,
                        precio_venta_momento=precio,
                    )
                    total_venta += precio * cantidad
                    total_items += 1

                Venta.objects.filter(pk=venta.pk).update(total=total_venta)
                total_ventas += 1

        self.stdout.write(f"   ✓ {total_ventas} ventas creadas, {total_items} items en total ({len(sucursales_nombres)} sucursales × 10)")

    # ─────────────────────────────────────────────────────────────────────────
    # RESUMEN FINAL
    # ─────────────────────────────────────────────────────────────────────────

    def _print_summary(self, users_map):
        self.stdout.write("\n" + "─" * 55)
        self.stdout.write(self.style.SUCCESS("  RESUMEN DE ACCESO"))
        self.stdout.write("─" * 55)
        self.stdout.write(f"  {'ROL':<14} {'USERNAME':<20} {'PASSWORD'}")
        self.stdout.write("─" * 55)
        rows = [
            ("admin",         "admin",          "admin1234"),
            ("sucursal",      "KioscoCampo",    "KioscoCampo1234"),
            ("sucursal",      "KioscoCentro",   "KioscoCentro1234"),
            ("sucursal",      "ComedorCampo",   "ComedorCampo1234"),
            ("sucursal",      "ComedorCentro",  "ComedorCentro1234"),
            ("sucursal",      "Hidrocinetic",   "Hidrocinetic1234"),
        ]
        for rol, user, pwd in rows:
            self.stdout.write(f"  {rol:<14} {user:<20} {pwd}")
        self.stdout.write("─" * 55)
