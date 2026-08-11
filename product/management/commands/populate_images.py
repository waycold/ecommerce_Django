import os
import time
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from product.models import Item, Category, Brand, Supplier
from faker import Faker

# Lista de URLs de imágenes de productos de ejemplo (Amazon/Unsplash) por si no se provee un archivo
DEFAULT_AMAZON_IMAGES = [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1532298229144-0ec0c57515c7?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1581235720704-06d3acfcb36f?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1504274066651-8d31a536b11a?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1572635196237-14b3f281501f?w=800&auto=format&fit=crop&q=80",
]

class Command(BaseCommand):
    help = "Pobla la base de datos con productos y descarga imágenes para subirlas a Cloudinary."

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Número de productos a procesar/crear (por defecto 10 para pruebas, soporta hasta 2000).'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Tiempo de espera en segundos (sleep) entre peticiones para evitar rate limiting.'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Si se activa, busca items existentes en la base de datos que no tengan imagen y les asigna una.'
        )
        parser.add_argument(
            '--url-file',
            type=str,
            default=None,
            help='Ruta opcional a un archivo de texto con una URL de imagen por línea.'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        delay = options['delay']
        update_existing = options['update_existing']
        url_file = options['url_file']

        fake = Faker()

        # Cargar URLs de imágenes
        image_urls = []
        if url_file and os.path.exists(url_file):
            self.stdout.write(self.style.SUCCESS(f"Cargando URLs desde el archivo: {url_file}"))
            with open(url_file, 'r', encoding='utf-8') as f:
                image_urls = [line.strip() for line in f if line.strip().startswith('http')]
        
        if not image_urls:
            self.stdout.write(self.style.WARNING("No se proveyó archivo de URLs o está vacío. Usando lista de URLs por defecto."))
            image_urls = DEFAULT_AMAZON_IMAGES

        # Asegurar que existan categorías, marcas y proveedores de prueba
        if not Category.objects.exists():
            for name in ['Electrónica', 'Hogar', 'Moda', 'Deportes', 'Juguetes']:
                Category.objects.create(name=name)
        if not Brand.objects.exists():
            for name in ['AmazonBasics', 'Samsung', 'Nike', 'Sony', 'Apple']:
                Brand.objects.create(name=name)
        if not Supplier.objects.exists():
            Supplier.objects.create(name='Amazon Logistics', country='USA')

        categories = list(Category.objects.all())
        brands = list(Brand.objects.all())
        supplier = Supplier.objects.first()

        self.stdout.write(f"Iniciando proceso. Límite: {limit} productos. Retardo: {delay}s por petición.")

        success_count = 0
        skipped_count = 0

        # Obtener los items a procesar
        items_to_process = []
        if update_existing:
            # Obtener items existentes sin imagen
            items_to_process = list(Item.objects.filter(img__isnull=True) | Item.objects.filter(img=''))[:limit]
            self.stdout.write(self.style.SUCCESS(f"Se encontraron {len(items_to_process)} productos existentes sin imagen para actualizar."))
        else:
            # Crear nuevos items temporales en memoria para procesar
            self.stdout.write(self.style.SUCCESS(f"Creando {limit} nuevos productos con Faker."))
            for i in range(limit):
                title = f"{fake.catch_phrase()} - {fake.word().capitalize()}"
                price = fake.pydecimal(left_digits=3, right_digits=2, min_value=10, max_value=999)
                cost = price * fake.pydecimal(left_digits=0, right_digits=2, min_value=0.4, max_value=0.7)
                
                item = Item(
                    title=title[:100],
                    description=fake.paragraph(nb_sentences=3)[:500],
                    price=price,
                    cost=cost,
                    stock=fake.random_int(min=5, max=150),
                    minimum_stock=10,
                    category=fake.random_element(categories),
                    brand=fake.random_element(brands),
                    supplier=supplier,
                    label=fake.random_element(['P', 'S', 'D', None]),
                    is_active=True
                )
                items_to_process.append(item)

        # Procesar imágenes
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }

        for idx, item in enumerate(items_to_process):
            # Obtener una URL de la lista de forma rotativa o aleatoria
            url = image_urls[idx % len(image_urls)]
            
            # Nombre de la imagen para almacenar en Cloudinary (limitado para no exceder varchar(100) del ImageField)
            clean_title = slugify(item.title)[:40]
            # Determinar extensión o usar jpg por defecto
            extension = 'jpg'
            if '.' in url.split('/')[-1]:
                potential_ext = url.split('/')[-1].split('.')[-1].lower()
                if potential_ext in ['jpg', 'jpeg', 'png', 'webp', 'avif']:
                    extension = potential_ext
            
            image_name = f"product_{clean_title}_{int(time.time())}.{extension}"
            
            self.stdout.write(f"[{idx+1}/{len(items_to_process)}] Procesando: '{item.title}'")
            self.stdout.write(f"   -> Descargando imagen desde: {url}")

            try:
                # Descargar con timeout de 10 segundos para no colgar el script
                # (Nota: Amazon Review '23 u otros datasets reales pueden tener URLs rotas o con timeout)
                response = requests.get(url, headers=headers, timeout=10)
                
                # Manejo robusto de errores HTTP
                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"   [!] Error HTTP {response.status_code} al descargar. Se omitirá/usará default."))
                    raise requests.HTTPError(f"HTTP Status {response.status_code}")

                # Guardar el contenido en un archivo de Django en memoria (ContentFile)
                content = ContentFile(response.content)
                
                # Si el item es nuevo, guardarlo primero en la BD para generar su ID
                if not item.pk:
                    item.save()

                # Guardar la imagen en el campo ImageField. Django-cloudinary-storage lo sube a Cloudinary automáticamente.
                item.img.save(image_name, content, save=False)
                item.save(update_fields=['img'])
                
                self.stdout.write(self.style.SUCCESS(f"   [+] Imagen subida exitosamente a Cloudinary para: '{item.title}'"))
                success_count += 1

            except (requests.RequestException, requests.HTTPError) as e:
                # Captura timeouts, 404s, errores DNS, etc.
                self.stdout.write(self.style.ERROR(f"   [!] Error de red al descargar la imagen: {e}"))
                self.assign_default_fallback(item, clean_title)
                skipped_count += 1
            except Exception as e:
                # Captura errores inesperados de Cloudinary, Pillow o la base de datos
                self.stdout.write(self.style.ERROR(f"   [!] Error inesperado en el proceso: {e}"))
                self.assign_default_fallback(item, clean_title)
                skipped_count += 1

            # Retardo para evitar sobrecargar la API (rate limit de Cloudinary / Amazon)
            if idx < len(items_to_process) - 1:
                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(
            f"\n--- PROCESO TERMINADO ---\n"
            f"Exitosos: {success_count}\n"
            f"Con error/Default asignado: {skipped_count}\n"
            f"Total procesados: {len(items_to_process)}"
        ))

    def assign_default_fallback(self, item, clean_title):
        """
        Asigna una imagen por defecto o ruta vacía de fallback.
        En producción o entorno real, se suele asignar una ruta estática o un archivo default pre-cargado.
        """
        try:
            # Opción A: Guardar el producto con img=None o vacío, permitiendo que el frontend renderice el default estático.
            # Opción B: Asignar una ruta preestablecida
            item.img = 'products/default.jpg'
            if not item.pk:
                item.save()
            else:
                item.save(update_fields=['img'])
            self.stdout.write(self.style.WARNING(f"   [Fallback] Asignada imagen por defecto 'products/default.jpg' para '{item.title}'"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [!] No se pudo guardar el fallback para '{item.title}': {e}"))
