import requests
from bs4 import BeautifulSoup
import pdfkit
import os
import time
import argparse
from PyPDF2 import PdfMerger
import re
from urllib.parse import urljoin, urlparse

def iniciar_sesion(url_login, usuario, contrasena):
    session = requests.Session()
    
    # Obtener el formulario de login para extraer tokens CSRF si los hay
    login_page = session.get(url_login)
    soup = BeautifulSoup(login_page.text, 'html.parser')
    
    # Buscar campo de token CSRF (nombre puede variar según el sitio)
    csrf_token = None
    csrf_field = soup.find('input', {'name': 'csrf_token'})  # Ajustar según el sitio
    if csrf_field:
        csrf_token = csrf_field.get('value')
    
    # Datos de login
    login_data = {
        'Username': usuario,
        'Password': contrasena
    }
    
    # Añadir token CSRF si existe
    if csrf_token:
        login_data['csrf_token'] = csrf_token
    
    # Enviar solicitud de login
    response = session.post(url_login, data=login_data)
    
    # Verificar login exitoso (ajustar según el comportamiento del sitio)
    if "incorrect" in response.text.lower() or "invalid" in response.text.lower():
        print("Error de inicio de sesión")
        return None
    
    return session

def descargar_pagina(url, nombre_archivo, session=None):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        if session:
            response = session.get(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            # Guardar el HTML
            with open(f"{nombre_archivo}.html", "w", encoding="utf-8") as file:
                file.write(response.text)
            return response.text
        else:
            print(f"Error al descargar {url}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error en la descarga de {url}: {e}")
        return None

def html_a_pdf(html_contenido, output_path, pagina_titulo="Documentación", opciones_adicionales=None):
    # Configurar opciones de PDF
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        'title': pagina_titulo,
        'enable-javascript': True,
        'javascript-delay': 2000,  # esperar 2 segundos para JavaScript
        'no-outline': None,
        'quiet': ''
    }
    
    # Añadir opciones adicionales si se proporcionan
    if opciones_adicionales:
        options.update(opciones_adicionales)
    
    # Guardar el PDF
    try:
        pdfkit.from_string(html_contenido, output_path, options=options)
        print(f"PDF guardado como: {output_path}")
        return True
    except Exception as e:
        print(f"Error al convertir a PDF: {e}")
        return False

def limpiar_html(html, selector_contenido):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extraer título
    titulo = soup.title.string if soup.title else "Documentación"
    
    # Extraer contenido relevante según el selector proporcionado
    if selector_contenido:
        # Si el selector comienza con #, buscar por id
        if selector_contenido.startswith('#'):
            contenido = soup.find(id=selector_contenido[1:])
        # Si el selector comienza con ., buscar por clase
        elif selector_contenido.startswith('.'):
            contenido = soup.find(class_=selector_contenido[1:])
        # De lo contrario, buscar por nombre de etiqueta
        else:
            contenido = soup.find(selector_contenido)
    else:
        # Intentar encontrar el contenido principal
        for selector in ['main', 'article', 'div.content', 'div#content', 'div.main-content', 'div#main']:
            if selector.startswith('div.'):
                contenido = soup.find('div', class_=selector[4:])
            elif selector.startswith('div#'):
                contenido = soup.find('div', id=selector[4:])
            else:
                contenido = soup.find(selector)
            
            if contenido:
                break
        else:
            # Si no se encuentra ningún contenedor principal específico, usar el body
            contenido = soup.body
    
    if contenido:
        # Crear un HTML limpio con solo el contenido relevante
        html_limpio = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{titulo}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                img {{ max-width: 100%; height: auto; }}
                pre {{ background-color: #f6f8fa; padding: 1em; border-radius: 5px; overflow-x: auto; }}
                code {{ font-family: monospace; }}
                h1 {{ font-size: 2em; color: #333; }}
                h2 {{ font-size: 1.5em; color: #444; }}
                h3 {{ font-size: 1.17em; color: #555; }}
                table {{ border-collapse: collapse; width: 100%; }}
                table, th, td {{ border: 1px solid #ddd; }}
                th, td {{ padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                a {{ color: #0366d6; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            {contenido}
        </body>
        </html>
        """
        return html_limpio, titulo
    else:
        print("No se encontró el contenido principal en la página.")
        return html, titulo

def extraer_y_convertir(url, nombre_base, session=None, selector_contenido=None):
    # Descargar la página
    html = descargar_pagina(url, nombre_base, session)
    
    if html:
        # Limpiar HTML y obtener contenido relevante
        html_limpio, titulo = limpiar_html(html, selector_contenido)
        
        # Guardar versión limpia del HTML
        with open(f"{nombre_base}_limpio.html", "w", encoding="utf-8") as file:
            file.write(html_limpio)
        
        # Convertir a PDF
        return html_a_pdf(html_limpio, f"{nombre_base}.pdf", titulo)
    return False

def es_url_valida(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def obtener_enlaces_documentacion(url_base, session=None, selector_menu=None, patron_url=None):
    try:
        if session:
            response = session.get(url_base)
        else:
            response = requests.get(url_base)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar enlaces según el selector de menú proporcionado
            if selector_menu:
                # Si el selector comienza con #, buscar por id
                if selector_menu.startswith('#'):
                    menu = soup.find(id=selector_menu[1:])
                # Si el selector comienza con ., buscar por clase
                elif selector_menu.startswith('.'):
                    menu = soup.find(class_=selector_menu[1:])
                # De lo contrario, buscar por nombre de etiqueta
                else:
                    menu = soup.find(selector_menu)
                
                if menu:
                    elementos = menu.find_all('a')
                else:
                    elementos = soup.find_all('a')
            else:
                elementos = soup.find_all('a')
            
            enlaces = []
            for link in elementos:
                href = link.get('href')
                
                # Verificar que el enlace existe
                if not href:
                    continue
                
                # Convertir enlaces relativos a absolutos
                href = urljoin(url_base, href)
                
                # Verificar si el enlace es válido según el patrón proporcionado
                if patron_url:
                    if re.search(patron_url, href):
                        enlaces.append(href)
                else:
                    # Filtrar enlaces que apuntan a la misma web
                    parsed_base = urlparse(url_base)
                    parsed_href = urlparse(href)
                    if parsed_base.netloc == parsed_href.netloc:
                        enlaces.append(href)
            
            return enlaces
        else:
            print(f"Error al acceder a la página principal: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error al obtener enlaces: {e}")
        return []

def combinar_pdfs(directorio):
    # Buscar todos los archivos PDF
    pdfs = [f for f in os.listdir(directorio) if f.endswith('.pdf') and f != "documentacion_completa.pdf"]
    
    if not pdfs:
        print("No se encontraron archivos PDF para combinar.")
        return False
    
    try:
        merger = PdfMerger()
        
        # Ordenar alfabéticamente
        pdfs.sort()
        
        # Añadir cada PDF al combinador
        for pdf in pdfs:
            merger.append(os.path.join(directorio, pdf))
        
        # Guardar el PDF combinado
        merger.write(os.path.join(directorio, "documentacion_completa.pdf"))
        merger.close()
        print(f"PDFs combinados en: {os.path.join(directorio, 'documentacion_completa.pdf')}")
        return True
    except Exception as e:
        print(f"Error al combinar PDFs: {e}")
        return False

def descargar_documentacion_completa(url_base, directorio_salida="documentacion", 
                                     selector_menu=None, selector_contenido=None, 
                                     patron_url=None, session=None, retraso=1):
    # Crear directorio de salida
    if not os.path.exists(directorio_salida):
        os.makedirs(directorio_salida)
    
    # Obtener enlaces
    enlaces = obtener_enlaces_documentacion(url_base, session, selector_menu, patron_url)
    print(f"Se encontraron {len(enlaces)} páginas de documentación.")
    
    # Eliminar duplicados
    enlaces = list(dict.fromkeys(enlaces))
    print(f"Después de eliminar duplicados: {len(enlaces)} páginas únicas.")
    
    # Descargar cada página
    for i, url in enumerate(enlaces):
        print(f"Procesando página {i+1}/{len(enlaces)}: {url}")
        nombre_archivo = os.path.join(directorio_salida, f"doc_{i+1:03d}")
        extraer_y_convertir(url, nombre_archivo, session, selector_contenido)
        
        # Esperar un poco entre solicitudes para no sobrecargar el servidor
        if i < len(enlaces) - 1:  # No esperar después de la última página
            time.sleep(retraso)
    
    # Combinar todos los PDFs en uno solo
    return combinar_pdfs(directorio_salida)

def main():
    parser = argparse.ArgumentParser(description='Descargar documentación web y convertirla a PDF.')
    parser.add_argument('url', help='URL base de la documentación')
    parser.add_argument('--output', '-o', default='documentacion', help='Directorio de salida')
    parser.add_argument('--menu', '-m', help='Selector CSS para el menú de navegación')
    parser.add_argument('--content', '-c', help='Selector CSS para el contenido principal')
    parser.add_argument('--pattern', '-p', help='Patrón regex para filtrar URLs')
    parser.add_argument('--login', '-l', help='URL de la página de login')
    parser.add_argument('--user', '-u', help='Nombre de usuario')
    parser.add_argument('--password', '-pw', help='Contraseña')
    parser.add_argument('--delay', '-d', type=int, default=1, help='Retraso en segundos entre solicitudes')
    
    args = parser.parse_args()
    print(args)
    
    # Verificar URL base
    if not es_url_valida(args.url):
        print("Error: La URL base proporcionada no es válida.")
        return
    
    session = None
    
    # Iniciar sesión si se proporcionaron credenciales
    if args.login and args.user and args.password:
        print(f"Iniciando sesión como {args.user}...")
        session = iniciar_sesion(args.login, args.user, args.password)
        if not session:
            print("Error al iniciar sesión. Continuando como usuario anónimo.")
    
    # Descargar documentación
    print(f"Descargando documentación desde {args.url} a {args.output}...")
    descargar_documentacion_completa(
        args.url, 
        args.output,
        args.menu,
        args.content,
        args.pattern,
        session,
        args.delay
    )

if __name__ == "__main__":
    main()