from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Q
from apps.users.permissions import IsAdminUser
from .models import Producto, Categoria
from .serializers import ProductoSerializer, CategoriaSerializer

class ProductoViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de productos.
    Lectura: todos los usuarios autenticados
    Escritura: solo administradores
    """
    queryset = Producto.objects.all().select_related('categoria')
    serializer_class = ProductoSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtro por tipo de producto fabricable/normal
        es_fabricable = self.request.query_params.get('es_fabricable')
        if es_fabricable is not None:
            if es_fabricable.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(es_fabricable=True)
            elif es_fabricable.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(es_fabricable=False)

        # Filtro opcional por tipo de conservación
        tipo = self.request.query_params.get('tipo_conservacion')
        if tipo:
            queryset = queryset.filter(tipo_conservacion=tipo)
        # Filtro por categoría
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        # Búsqueda por nombre
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(nombre__icontains=search) | Q(sku__icontains=search))

        queryset = queryset.order_by('nombre')

        # Límite opcional para autocompletados
        limit = self.request.query_params.get('limit')
        if limit and str(limit).isdigit():
            queryset = queryset[: min(int(limit), 50)]

        return queryset

class CategoriaViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de categorías de productos.
    Lectura: todos los usuarios autenticados
    Escritura: solo administradores
    """
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticatedOrReadOnly()]
        return [IsAdminUser()]
