# Pantallas

**Pantallas** es una aplicación de escritorio para Windows, escrita en Python, para visualizar y organizar monitores y mantener aplicaciones fijadas a una zona concreta de una pantalla.

## V0.2

- Detecta todos los monitores activos.
- Muestra resolución, orientación, coordenadas y monitor principal.
- Permite arrastrar los monitores en un lienzo y aplicar esa distribución a Windows.
- Permite cambiar entre orientación horizontal, vertical, horizontal invertida y vertical invertida.
- Control de brillo independiente mediante DDC/CI cuando el monitor lo soporta.
- Encendido/apagado individual mediante DDC/CI (VCP 0xD6) cuando el monitor lo soporta.
- Lista las ventanas abiertas y detecta en qué monitor están.
- Crea reglas persistentes por aplicación/ventana.
- Las reglas guardan monitor y geometría como porcentajes del área útil, por lo que funcionan bien con monitores de resoluciones distintas.
- Un motor de reglas vuelve a colocar automáticamente las ventanas que se muevan.
- La aplicación puede quedarse en la bandeja del sistema mientras mantiene las reglas activas.
- Busca actualizaciones automáticamente al iniciar y cada 30 minutos mientras está abierta.
- Incluye el botón **Buscar actualizaciones** dentro de la aplicación.
- Las actualizaciones se descargan desde GitHub Releases, se validan por SHA-256, cierran Pantallas, se instalan silenciosamente y vuelven a abrir la aplicación.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior recomendado.
- Para brillo/energía en monitores externos: DDC/CI habilitado en el menú del monitor.
- Algunos monitores, docks, adaptadores DisplayLink, HDMI/DP y KVM no exponen DDC/CI. Pantallas detecta esa limitación y no fuerza un método inseguro.

## Ejecutar desde Python

```powershell
git clone https://github.com/Yakoderaa/Pantallas.git
cd Pantallas
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Instalador y actualizaciones

El workflow de GitHub Actions `build-windows.yml` genera `Pantallas.exe`, crea `PantallasSetup.exe` con Inno Setup y publica el instalador junto con su checksum SHA-256 en GitHub Releases.

Cada push nuevo a `main` genera un nuevo build publicable. El workflow usa concurrencia con cancelación para evitar publicar builds intermedios cuando se suben varios archivos consecutivamente.

La aplicación consulta la release más reciente. Si detecta un build superior al instalado, descarga `PantallasSetup.exe`, verifica el checksum y lanza el instalador después de cerrar la aplicación. El instalador vuelve a abrir Pantallas cuando termina.

## Cómo crear una regla

1. Abrí **Ventanas y reglas**.
2. Seleccioná la ventana, por ejemplo Discord.
3. Elegí el monitor de destino.
4. Indicá X, Y, ancho y alto en porcentajes o usá **Capturar posición actual**.
5. Guardá la regla.
6. Mientras **Bloqueo automático** esté activo, Pantallas comprobará la posición y la restaurará cuando cambie.

## Notas sobre apagado individual

Windows no ofrece una API universal para apagar físicamente un solo monitor externo. Pantallas usa el estándar DDC/CI/MCCS para hacerlo por monitor. En hardware compatible funciona de forma independiente; en hardware que no expone ese canal el botón se desactiva. El encendido por software puede no ser aceptado por algunos modelos una vez que el panel entra en reposo profundo.
