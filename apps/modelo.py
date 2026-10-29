import asyncio

import flet as ft

from ia import ia


INSTRUCCION = (
    "Genera exactamente tres excusas de una sola frase sobre lo que le pasó "
    "al usuario: una creíble, una épica y una absurda. Devuelve únicamente "
    "un objeto JSON con las claves \"creible\", \"epica\" y \"absurda\", "
    "cada una con una cadena de texto."
)


def vista():
    situacion = ft.TextField(
        label="¿Qué pasó?",
        hint_text="Cuéntame brevemente qué pasó",
        multiline=True,
        min_lines=2,
        max_lines=4,
        expand=True,
    )
    mensaje = ft.Text()
    resultados = ft.Column(spacing=8)
    boton = ft.Button("Crear excusas")
    vista_app = ft.Column(
        controls=[
            ft.Text("Excusas", size=28, weight=ft.FontWeight.BOLD),
            situacion,
            boton,
            mensaje,
            resultados,
        ],
        spacing=16,
        expand=True,
    )

    async def crear_excuses(_):
        texto = (situacion.value or "").strip()
        if not texto:
            mensaje.value = "Escribe qué pasó para poder crear las excusas."
            resultados.controls.clear()
            vista_app.update()
            return

        boton.disabled = True
        mensaje.value = "Creando excusas..."
        resultados.controls.clear()
        vista_app.update()

        try:
            # Ejecuta la llamada bloqueante sin congelar la interfaz.
            respuesta = await asyncio.to_thread(
                ia, INSTRUCCION, texto, como_json=True
            )
            tipos = (
                ("Creíble", "creible"),
                ("Épica", "epica"),
                ("Absurda", "absurda"),
            )
            if not isinstance(respuesta, dict) or any(
                not isinstance(respuesta.get(clave), str)
                or not respuesta[clave].strip()
                for _, clave in tipos
            ):
                raise ValueError("La respuesta no contiene las tres excusas.")

            resultados.controls.extend(
                ft.Text(f"{etiqueta}: {respuesta[clave].strip()}")
                for etiqueta, clave in tipos
            )
            mensaje.value = ""
        except Exception:
            # Muestra un aviso sencillo sin exponer detalles técnicos.
            mensaje.value = (
                "No pude crear las excusas. Inténtalo de nuevo en un momento."
            )
        finally:
            boton.disabled = False
            vista_app.update()

    boton.on_click = crear_excuses
    return vista_app