# Pantallas

**Pantallas** es una aplicación de escritorio para Windows, escrita en Python, para visualizar y organizar monitores y mantener aplicaciones fijadas a una zona concreta de una pantalla.

## V0.5

- Detecta todos los monitores activos.
- Muestra resolución, orientación, coordenadas y monitor principal.
- La sección **Monitores** integra ahora dos vistas: **Control** y **Distribución**.
- Permite arrastrar los monitores en un lienzo y aplicar esa distribución a Windows.
- Permite asignar nombres personalizados a los monitores; esos nombres se usan también en la bandeja y en la interfaz.
- Permite cambiar entre orientación horizontal, vertical, horizontal invertida y vertical invertida.
- Control de brillo independiente mediante DDC/CI cuando el monitor lo soporta.
- El apagado individual verifica si Windows realmente desactivó la salida. Si el controlador la deja activa, Pantallas usa el comando físico DDC/CI como respaldo y guarda el método utilizado para poder encenderla después.
- Pantallas nunca permite apagar la última pantalla activa.
- Si se apaga la pantalla donde está abierta la aplicación, Pantallas se mueve antes a otra pantalla activa.
- Las pantallas apagadas quedan disponibles para volver a encenderlas desde la aplicación o desde la bandeja.
- Lista las ventanas abiertas y detecta en qué monitor están.
- Crea reglas persistentes por aplicación/ventana.
- Las reglas guardan monitor y geometría como porcentajes del área útil.
- Un motor de reglas vuelve a colocar automáticamente las ventanas que se muevan.
- Puede iniciarse automáticamente con Windows.
- Puede iniciarse minimizada en la bandeja del sistema.
- El icono de bandeja tiene menú contextual con accesos rápidos por monitor: abrir/configurar, brillo, apagar o encender.
- Busca actualizaciones automáticamente al iniciar y cada 30 minutos mientras está abierta.
- Incluye el botón **Buscar actualizaciones** dentro de la aplicación.
- Las actualizaciones se descargan desde GitHub Releases, se validan por SHA-256, cierran Pantallas, se instalan silenciosamente y vuelven a abrir la aplicación.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior recomendado.
- Para control de brillo en monitores externos: DDC/CI habilitado en el menú del monitor.
- Algunos monitores, docks, adaptadores DisplayLink, HDMI/DP y KVM no exponen DDC/CI; en esos casos el brillo puede no estar disponible.

## Inicio con Windows

En la pestaña **Configuración** podés activar **Iniciar Pantallas con Windows** y **Iniciar minimizada en la bandeja**.

También podés cambiar ambas opciones desde el menú contextual del icono de Pantallas en la bandeja de Windows.

## Menú rápido de bandeja

Con clic derecho sobre el icono de Pantallas aparecen:

- **Abrir Pantallas**
- Un submenú por cada monitor activo
  - Abrir y configurar ahí
  - Brillo 25/50/75/100 %
  - Apagar monitor
- Un submenú por cada monitor apagado
  - Encender monitor
- Iniciar con Windows
- Iniciar minimizada
- Buscar actualizaciones
- Salir

## Ejecutar desde Python

```powershell
git clone https://github.com/Yakoderaa/Pantallas.git
cd Pantallas
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Para probar el inicio minimizado:

```powershell
python app.py --minimized
```

## Instalador y actualizaciones

El workflow de GitHub Actions `build-windows.yml` genera `Pantallas.exe`, crea `PantallasSetup.exe` con Inno Setup y publica el instalador junto con su checksum SHA-256 en GitHub Releases.

Cada push nuevo a `main` genera un nuevo build publicable. La aplicación consulta la release más reciente y, si detecta un build superior al instalado, descarga `PantallasSetup.exe`, verifica el checksum y lanza el instalador después de cerrar la aplicación.

## Cómo crear una regla

1. Abrí **Ventanas y reglas**.
2. Seleccioná la ventana, por ejemplo Discord.
3. Elegí el monitor de destino.
4. Indicá X, Y, ancho y alto en porcentajes o usá **Capturar posición actual**.
5. Guardá la regla.
6. Mientras **Bloqueo automático** esté activo, Pantallas comprobará la posición y la restaurará cuando cambie.

## Notas sobre encendido y apagado

En V0.5 Pantallas prueba primero a retirar la salida del escritorio de Windows y comprueba el resultado. Si el controlador informa éxito pero el monitor sigue activo, restaura la señal normal y usa DDC/CI para apagar físicamente el panel. El método usado queda guardado junto con resolución, posición y orientación.

Al volver a encender un monitor apagado por DDC/CI, Pantallas intenta primero el comando de energía, luego fuerza un despertar de pantallas desde Windows y vuelve a adquirir un handle DDC/CI nuevo. Esto mejora la compatibilidad con monitores que dejan de responder durante el reposo.

El control de **brillo** sigue usando DDC/CI.
