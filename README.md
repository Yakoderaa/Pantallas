# Pantallas

**Pantallas** es una aplicación de escritorio para Windows, escrita en Python, para visualizar y organizar monitores y mantener aplicaciones fijadas a una zona concreta de una pantalla.

## V0.7

- Detecta todos los monitores activos.
- Muestra resolución, orientación, coordenadas y monitor principal.
- La vista Control muestra también un mapa visible de la distribución actual.
- Los monitores pueden reordenarse manualmente con **Subir** y **Bajar**; el orden se guarda y se reutiliza en menús y selectores.
- Permite asignar nombres personalizados a los monitores; esos nombres se usan también en la bandeja y en la interfaz.
- Control de brillo independiente mediante DDC/CI cuando el monitor lo soporta.
- El apagado individual verifica si Windows realmente desactivó la salida. Si el controlador la deja activa, Pantallas usa el comando físico DDC/CI como respaldo y guarda el método utilizado para poder encenderla después.
- Por defecto Pantallas nunca permite apagar la última pantalla activa y muestra un aviso al intentarlo.
- En Configuración se puede permitir apagar todos los monitores, con una advertencia explícita antes de desactivar la protección.
- Si se apaga la pantalla donde está abierta la aplicación, Pantallas se mueve antes a otra pantalla activa.
- Las pantallas apagadas quedan disponibles para volver a encenderlas desde la aplicación o desde la bandeja.
- Lista las ventanas abiertas y detecta en qué monitor están.
- Crea reglas persistentes por aplicación/ventana.
- Las reglas guardan monitor y geometría como porcentajes del área útil.
- Un motor de reglas vuelve a colocar automáticamente las ventanas que se muevan.
- Puede iniciarse automáticamente con Windows.
- Puede iniciarse minimizada en la bandeja del sistema.
- El icono de bandeja tiene menú contextual con accesos rápidos por monitor: abrir Pantallas ahí, brillo, apagar o encender.
- La bandeja incluye un tic **Bloqueo de posiciones** para pausar o reactivar todas las restricciones de posición de aplicaciones.
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
  - Abrir Pantallas ahí
  - Brillo 25/50/75/100 %
  - Apagar monitor
- Un submenú por cada monitor apagado
  - Encender monitor
- **Bloqueo de posiciones** (tic global)
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
6. Mientras **Bloqueo de posiciones** esté activo, Pantallas comprobará la posición y la restaurará cuando cambie.

## Notas sobre encendido y apagado

En V0.7 Pantallas intenta primero un standby DDC/CI reversible. Si el monitor no acepta control de energía por DDC, recién entonces intenta desactivar su salida desde Windows. Los estados DDC standby/suspend/off permanecen marcados como apagados aunque Windows siga conservando el monitor en su topología lógica. El método usado queda guardado junto con resolución, posición y orientación.

Al volver a encender un monitor apagado por DDC/CI, Pantallas restaura primero la señal de Windows, fuerza un despertar, vuelve a adquirir handles DDC/CI nuevos y reintenta varias veces. Los nuevos apagados DDC usan standby (0x02) antes que deep-off (0x04) para conservar la capacidad de despertar. Los monitores guardados por versiones anteriores en deep-off reciben además una renegociación HDMI/DisplayPort. Esto mejora la compatibilidad con monitores que dejan de responder durante el reposo.

El control de **brillo** sigue usando DDC/CI.


## Recuperación de brillo

Pantallas guarda el último brillo válido de cada monitor. Si DDC/CI tarda en volver después de encender una pantalla, la interfaz conserva ese valor en lugar de mostrar 0 o N/D y refresca el monitor varias veces hasta que el canal de control vuelve a responder.
