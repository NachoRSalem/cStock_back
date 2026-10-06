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
        # Búsqueda flexible por nombre, SKU o categoría
        search = self.request.query_params.get('search')
        if search:
            search_str = search.strip()
            # Término directo
            q_filter = Q(nombre__icontains=search_str) | Q(sku__icontains=search_str) | Q(categoria__nombre__icontains=search_str)
            
            # Normalizar caracteres especiales (guiones, guiones bajos a espacio) y buscar por palabras
            normalized_terms = search_str.replace('-', ' ').replace('_', ' ').split()
            if len(normalized_terms) > 1:
                term_q = Q()
                for term in normalized_terms:
                    term_q &= (Q(nombre__icontains=term) | Q(sku__icontains=term) | Q(categoria__nombre__icontains=term))
                q_filter |= term_q

            # Reemplazar espacios por guiones (ej: "coca cola" -> "coca-cola")
            hyphenated = search_str.replace(' ', '-')
            if hyphenated != search_str:
                q_filter |= Q(nombre__icontains=hyphenated)

            queryset = queryset.filter(q_filter)

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
