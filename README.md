# Pantallas

**Pantallas** es una aplicación de escritorio para Windows, escrita en Python, para visualizar y organizar monitores y mantener aplicaciones fijadas a una zona concreta de una pantalla.

## V0.1

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

## EXE

El workflow de GitHub Actions `build-windows.yml` genera `Pantallas.exe` como artefacto de Windows.

## Cómo crear una regla

1. Abrí **Ventanas y reglas**.
2. Seleccioná la ventana, por ejemplo Discord.
3. Elegí el monitor de destino.
4. Indicá X, Y, ancho y alto en porcentajes o usá **Capturar posición actual**.
5. Guardá la regla.
6. Mientras **Bloqueo automático** esté activo, Pantallas comprobará la posición y la restaurará cuando cambie.

## Notas sobre apagado individual

Windows no ofrece una API universal para apagar físicamente un solo monitor externo. Pantallas usa el estándar DDC/CI/MCCS para hacerlo por monitor. En hardware compatible funciona de forma independiente; en hardware que no expone ese canal el botón se desactiva. El encendido por software puede no ser aceptado por algunos modelos una vez que el panel entra en reposo profundo.
