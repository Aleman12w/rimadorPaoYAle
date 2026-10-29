import asyncio
import base64
import mimetypes
import re
from urllib.parse import quote, urlsplit

import flet as ft
from flet_audio_recorder import (
    AudioEncoder,
    AudioRecorder,
    AudioRecorderConfiguration,
)

from ia import ia
from multimedia import ia_media, ia_multimedia, pcm_a_wav


INSTRUCCION = (
    "Escribe una rima original sobre la entrada indicada, formada exactamente "
    "por cuatro versos que rimen entre sí. Devuelve únicamente un objeto JSON "
    "con las claves \"titulo\", \"verso1\", \"verso2\", \"verso3\", \"verso4\" "
    "y \"estilo\". Todos los valores deben ser cadenas de texto; el estilo "
    "debe corresponder al solicitado."
)

INSTRUCCION_TRANSCRIPCION = (
    "Transcribe únicamente las palabras que dice la persona en el audio. "
    "Devuelve la transcripción en español, sin explicaciones ni comillas."
)

MAX_GENERACIONES = 10

PATRONES_DATOS_SENSIBLES = (
    (
        "una contraseña o clave de acceso",
        re.compile(
            r"\b(?:contrase(?:ña|na)|password|passwd|passcode|clave)"
            r"\s*(?::|=)\s*\S+|\b(?:contrase(?:ña|na)|password|passwd|passcode|clave)"
            r"\s+es\s+\S+",
            re.IGNORECASE,
        ),
    ),
    (
        "un número de DUI",
        re.compile(r"(?<!\d)\d{8}(?:-|\s)?\d(?!\d)"),
    ),
    (
        "un número de teléfono",
        re.compile(
            r"(?<!\w)(?:\+?503[\s.-]?)?(?:[267]\d{3})[\s.-]?\d{4}(?!\w)"
            r"|(?<!\w)\+?\d{1,3}(?:[\s().-]*\d){7,12}(?!\w)"
        ),
    ),
)

DETALLE_ESTILOS = {
    "rap": (
        "usa barras rítmicas, lenguaje urbano y rimas contundentes, "
        "incluidas rimas internas cuando encajen"
    ),
    "bolero": (
        "usa un tono romántico y melódico, imágenes emotivas y frases "
        "líricas propias de una canción"
    ),
    "reguetón": (
        "usa cadencia urbana bailable, frases breves y rítmicas, y un "
        "vocabulario actual apropiado"
    ),
    "poesia_clasica": (
        "usa dicción poética clásica, cadencia regular y métrica cuidada, "
        "con imágenes y recursos literarios tradicionales"
    ),
}


def vista(page):
    tema = ft.TextField(
        label="Tema",
        hint_text="¿Sobre qué quieres una rima?",
        border_color=ft.Colors.CYAN_400,
        focused_border_color=ft.Colors.CYAN,
        label_style=ft.TextStyle(color=ft.Colors.CYAN_200),
        color=ft.Colors.WHITE,
        expand=True,
    )
    estilo = ft.Dropdown(
        label="Estilo",
        value="rap",
        options=[
            ft.DropdownOption(key="rap", text="Rap"),
            ft.DropdownOption(key="bolero", text="Bolero"),
            ft.DropdownOption(key="reguetón", text="Reguetón"),
            ft.DropdownOption(
                key="poesia_clasica",
                text="Poesía Clásica",
            ),
        ],
        border_color=ft.Colors.CYAN_400,
        focused_border_color=ft.Colors.CYAN,
        label_style=ft.TextStyle(color=ft.Colors.CYAN_200),
        text_style=ft.TextStyle(color=ft.Colors.WHITE),
        expand=True,
    )
    humor_valor = ft.Text(
        "Nivel de humor: 1/5",
        color=ft.Colors.CYAN_200,
    )
    humor = ft.Slider(
        min=1,
        max=5,
        divisions=4,
        value=1,
        label="{value}",
        active_color=ft.Colors.CYAN_400,
        thumb_color=ft.Colors.CYAN_300,
    )
    mensaje = ft.Text(color=ft.Colors.CYAN_200)
    poema = ft.Column(spacing=10)
    historial = []
    historial_vista = ft.ListView(
        height=260,
        spacing=10,
        auto_scroll=False,
    )
    historial_panel = ft.Column(
        controls=[
            ft.Text(
                "Historial de rimas",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.CYAN_200,
            ),
            historial_vista,
        ],
        spacing=8,
    )
    rima_actual = None
    me_gusta = 0
    no_me_gusta = 0
    calificacion_actual = None
    estadisticas_me_gusta = ft.Text(
        "👍 0",
        color=ft.Colors.GREEN_300,
        weight=ft.FontWeight.BOLD,
    )
    estadisticas_no_me_gusta = ft.Text(
        "👎 0",
        color=ft.Colors.PINK_300,
        weight=ft.FontWeight.BOLD,
    )
    boton_me_gusta = ft.Button(
        "👍",
        tooltip="Me gusta esta rima",
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.GREEN_300,
        disabled=True,
    )
    boton_no_me_gusta = ft.Button(
        "👎",
        tooltip="No me gusta esta rima",
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.PINK_300,
        disabled=True,
    )
    mensaje_calificacion = ft.Text(
        color=ft.Colors.GREY_400,
        size=12,
    )
    panel_estadisticas = ft.Card(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Estadísticas de esta sesión",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.CYAN_200,
                    ),
                    ft.Row(
                        controls=[
                            estadisticas_me_gusta,
                            estadisticas_no_me_gusta,
                        ],
                        spacing=24,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
        ),
        bgcolor=ft.Colors.GREY_800,
    )
    generaciones = 0
    uso_generaciones = ft.Text(
        f"Generaciones de esta sesión: 0/{MAX_GENERACIONES}",
        color=ft.Colors.GREY_400,
        size=12,
    )
    aviso_limite = ft.Card(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.INFO_OUTLINE,
                        color=ft.Colors.CYAN_300,
                    ),
                    ft.Text(
                        f"Alcanzaste el límite de {MAX_GENERACIONES} "
                        "generaciones de esta sesión. Podrás volver a crear "
                        "rimas cuando inicies una sesión nueva.",
                        color=ft.Colors.WHITE,
                        expand=True,
                    ),
                ],
                spacing=12,
            ),
            padding=14,
        ),
        bgcolor=ft.Colors.GREY_800,
        visible=False,
    )
    alerta_error_titulo = ft.Text(
        color=ft.Colors.PINK_300,
        weight=ft.FontWeight.BOLD,
    )
    alerta_error_detalle = ft.Text(color=ft.Colors.WHITE)
    alerta_error = ft.Card(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.ERROR_OUTLINE,
                        color=ft.Colors.PINK_400,
                    ),
                    ft.Column(
                        controls=[alerta_error_titulo, alerta_error_detalle],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=12,
            ),
            padding=14,
        ),
        bgcolor=ft.Colors.GREY_800,
        visible=False,
    )
    boton = ft.Button(
        "Crear rima",
        bgcolor=ft.Colors.CYAN_700,
        color=ft.Colors.WHITE,
    )
    boton_copiar = ft.Button(
        "Copiar Rima",
        icon=ft.Icons.COPY,
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.CYAN_200,
        disabled=True,
    )
    boton_escuchar = ft.Button(
        "Escuchar Rima",
        icon=ft.Icons.VOLUME_UP,
        tooltip="Reproducir la rima en español",
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.CYAN_200,
        disabled=True,
    )
    boton_microfono = ft.Button(
        "Grabar voz",
        icon=ft.Icons.MIC,
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.CYAN_200,
    )
    boton_foto = ft.Button(
        "Subir foto",
        icon=ft.Icons.IMAGE,
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.CYAN_200,
    )
    boton_foto_voz = ft.Button(
        "Rima con foto + voz",
        icon=ft.Icons.MIC,
        tooltip=(
            "Selecciona una foto, dicta instrucciones y pulsa otra vez "
            "para crear la rima"
        ),
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.PINK_300,
    )
    nombre_foto = ft.Text(color=ft.Colors.GREY_300)
    texto_leido_imagen = ft.Text(color=ft.Colors.WHITE)
    boton_texto = ft.Button(
        "Subir archivo .txt",
        icon=ft.Icons.UPLOAD_FILE,
        bgcolor=ft.Colors.GREY_800,
        color=ft.Colors.CYAN_200,
    )
    info_documento = ft.Text(color=ft.Colors.GREY_300)
    progreso = ft.ProgressRing(visible=False, width=22, height=22)
    trozos_audio = []
    grabando = False
    grabacion_combinada = False
    imagen_combinada = None
    tarea_limite = None

    def recibir_trozo(evento):
        # Cada evento contiene un fragmento PCM de 16 bits.
        if evento.chunk:
            trozos_audio.append(evento.chunk)

    grabadora = AudioRecorder(
        configuration=AudioRecorderConfiguration(
            encoder=AudioEncoder.PCM16BITS,
            sample_rate=16000,
            channels=1,
        ),
        on_stream=recibir_trozo,
    )
    if grabadora not in page.services:
        page.services.append(grabadora)

    selector = ft.FilePicker()
    if selector not in page.services:
        page.services.append(selector)

    portapapeles = ft.Clipboard()
    if portapapeles not in page.services:
        page.services.append(portapapeles)

    lanzador_url = ft.UrlLauncher()
    if lanzador_url not in page.services:
        page.services.append(lanzador_url)

    snackbar_copiado = ft.SnackBar(
        content="¡Rima copiada!",
        duration=2500,
        bgcolor=ft.Colors.GREY_800,
        open=False,
    )
    page.overlay.append(snackbar_copiado)

    banner_superior = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.MIC,
                            size=34,
                            color=ft.Colors.PINK_400,
                        ),
                        ft.Text(
                            "Rimador 🎤",
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.CYAN_300,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            "Convierte un tema, una idea o un documento en versos y rimas originales.",
                            color=ft.Colors.GREY_200,
                        ),
                        ft.Text(
                            "Personaliza el estilo y crea poemas breves de cuatro versos.",
                            color=ft.Colors.GREY_200,
                        ),
                        ft.Text(
                            "Puedes escuchar la rima; no genera canciones completas con audio musical.",
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    spacing=6,
                ),
            ],
            spacing=14,
        ),
        bgcolor=ft.Colors.GREY_900,
        border=ft.Border.all(1, ft.Colors.CYAN_800),
        border_radius=18,
        padding=22,
    )

    vista_app = ft.Container(
        content=ft.Column(
            controls=[
                banner_superior,
                ft.Text(
                    "La IA puede cometer errores. Verifica la información.",
                    color=ft.Colors.GREY_400,
                    size=12,
                ),
                uso_generaciones,
                aviso_limite,
                alerta_error,
                tema,
                estilo,
                humor_valor,
                humor,
                ft.Row(
                    controls=[                    ft.Row(
                        controls=[boton_foto, boton_foto_voz],
                        spacing=10,
                        wrap=True,
                    ), boton_foto_voz],
                    spacing=10,
                    wrap=True,
                ),
                nombre_foto,
                ft.Text(
                    "Texto leído de la imagen:",
                    color=ft.Colors.CYAN_200,
                    weight=ft.FontWeight.BOLD,
                ),
                texto_leido_imagen,
                boton_texto,
                info_documento,
                boton_microfono,
                boton,
                boton_copiar,
                progreso,
                mensaje,
                poema,
                ft.Row(
                    controls=[
                        ft.Text(
                            "¿Qué te pareció esta rima?",
                            color=ft.Colors.GREY_300,
                        ),
                        boton_me_gusta,
                        boton_no_me_gusta,
                        mensaje_calificacion,
                    ],
                    spacing=10,
                    wrap=True,
                ),
                historial_panel,
                panel_estadisticas,
            ],
            spacing=16,
            expand=True,
        ),
        bgcolor=ft.Colors.GREY_900,
        padding=20,
        border_radius=16,
        expand=True,
    )

    def actualizar_carga(cargando, texto=None, permitir_detener=False):
        # Mantiene bloqueadas las acciones durante el trabajo y permite detener la grabación.
        limite_alcanzado = generaciones >= MAX_GENERACIONES
        boton.disabled = cargando or limite_alcanzado
        boton_foto.disabled = cargando or limite_alcanzado
        boton_foto_voz.disabled = limite_alcanzado or (
            cargando and not (permitir_detener and grabacion_combinada)
        )
        boton_texto.disabled = cargando or limite_alcanzado
        boton_microfono.disabled = limite_alcanzado or grabacion_combinada or (
            cargando and not permitir_detener
        )
        boton_escuchar.disabled = cargando or rima_actual is None
        boton_me_gusta.disabled = (
            cargando
            or rima_actual is None
            or calificacion_actual is not None
        )
        boton_no_me_gusta.disabled = boton_me_gusta.disabled
        progreso.visible = cargando
        if texto is not None:
            mensaje.value = texto
        page.update()

    def actualizar_limite():
        limite_alcanzado = generaciones >= MAX_GENERACIONES
        uso_generaciones.value = (
            f"Generaciones de esta sesión: "
            f"{min(generaciones, MAX_GENERACIONES)}/{MAX_GENERACIONES}"
        )
        aviso_limite.visible = limite_alcanzado
        boton.disabled = boton.disabled or limite_alcanzado
        boton_foto.disabled = boton_foto.disabled or limite_alcanzado
        boton_foto_voz.disabled = boton_foto_voz.disabled or limite_alcanzado
        boton_texto.disabled = boton_texto.disabled or limite_alcanzado
        boton_microfono.disabled = boton_microfono.disabled or limite_alcanzado

    def mostrar_alerta(titulo, detalle):
        alerta_error_titulo.value = titulo
        alerta_error_detalle.value = detalle
        alerta_error.visible = True
        page.update()

    def explicar_error(error):
        detalle = str(error).casefold()
        tipo_error = type(error).__name__.casefold()
        if "api key not valid" in detalle or "invalid api key" in detalle:
            return (
                "Revisa la clave de acceso configurada para el servicio e "
                "inténtalo de nuevo."
            )
        if "falta gemini_api_key" in detalle:
            return (
                "El servicio de rimas todavía no está configurado. "
                "Pide ayuda al administrador de la aplicación."
            )
        if "http 429" in detalle or "status code 429" in detalle:
            return (
                "El servicio recibió demasiadas solicitudes o alcanzó su "
                "cuota. Espera un momento antes de volver a intentarlo."
            )
        if "http 400" in detalle or "status code 400" in detalle:
            return (
                "El servicio no pudo procesar esta petición. Prueba con un "
                "tema más breve o inténtalo de nuevo más tarde."
            )
        if any(
            palabra in detalle
            for palabra in (
                "network",
                "connection",
                "connect",
                "timeout",
                "timed out",
                "red",
                "dns",
                "unreachable",
            )
        ) or any(
            palabra in tipo_error
            for palabra in ("connect", "timeout", "network", "request")
        ):
            return (
                "No se pudo conectar con el servicio. Comprueba tu conexión "
                "a internet e inténtalo de nuevo."
            )
        return (
            "Ocurrió un problema al comunicarse con el servicio. "
            "Inténtalo de nuevo en un momento."
        )

    def nombre_estilo():
        return {
            "rap": "Rap",
            "bolero": "Bolero",
            "reguetón": "Reguetón",
            "poesia_clasica": "Poesía Clásica",
        }[estilo.value]

    def actualizar_humor(_):
        humor_valor.value = f"Nivel de humor: {int(humor.value)}/5"
        page.update()

    def validar_entrada(texto):
        texto = (texto or "").strip()
        if not texto:
            mensaje.value = "La entrada está vacía. Escribe o carga un tema."
            page.update()
            return None
        for descripcion, patron in PATRONES_DATOS_SENSIBLES:
            if patron.search(texto):
                mostrar_alerta(
                    "Entrada bloqueada por seguridad",
                    f"El texto parece incluir {descripcion}. Elimínalo antes "
                    "de solicitar una rima.",
                )
                return None
        if len(texto) > 500:
            mensaje.value = (
                f"La entrada tiene {len(texto)} caracteres; el máximo permitido es 500."
            )
            page.update()
            return None
        return texto

    def tarjetas_rima(rima):
        controles = [
            ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        rima["titulo"],
                                        size=22,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.CYAN_300,
                                        expand=True,
                                    ),
                                    boton_escuchar,
                                ],
                                spacing=12,
                            ),
                            ft.Text(
                                f"Estilo: {rima['estilo']}",
                                color=ft.Colors.GREY_300,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=16,
                ),
                bgcolor=ft.Colors.GREY_800,
                elevation=2,
            )
        ]
        controles.extend(
            ft.Card(
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                f"{numero}.",
                                color=ft.Colors.CYAN_300,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                rima[f"verso{numero}"],
                                color=ft.Colors.WHITE,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=14,
                ),
                bgcolor=ft.Colors.GREY_900,
                elevation=1,
            )
            for numero in range(1, 5)
        )
        return controles

    def actualizar_historial():
        historial_vista.controls.clear()
        for rima in reversed(historial):
            historial_vista.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    rima["titulo"],
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.CYAN_300,
                                ),
                                ft.Text(
                                    " · ".join(
                                        rima[f"verso{numero}"]
                                        for numero in range(1, 5)
                                    ),
                                    color=ft.Colors.WHITE,
                                ),
                                ft.Text(
                                    f"Estilo: {rima['estilo']}",
                                    color=ft.Colors.GREY_400,
                                    size=12,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=12,
                    ),
                    bgcolor=ft.Colors.GREY_800,
                    elevation=1,
                )
            )

    def registrar_calificacion(valor):
        nonlocal me_gusta, no_me_gusta, calificacion_actual
        if rima_actual is None or calificacion_actual is not None:
            return

        calificacion_actual = valor
        if valor == "positiva":
            me_gusta += 1
            estadisticas_me_gusta.value = f"👍 {me_gusta}"
        else:
            no_me_gusta += 1
            estadisticas_no_me_gusta.value = f"👎 {no_me_gusta}"

        boton_me_gusta.disabled = True
        boton_no_me_gusta.disabled = True
        mensaje_calificacion.value = "¡Gracias por tu opinión!"
        page.update()

    def calificar_positivamente(_):
        registrar_calificacion("positiva")

    def calificar_negativamente(_):
        registrar_calificacion("negativa")

    async def generar_rima(
        texto,
        instruccion_rima=None,
        gestionar_carga=True,
        archivos_multimedia=None,
    ):
        nonlocal rima_actual, generaciones, calificacion_actual

        texto = validar_entrada(texto)
        if texto is None:
            poema.controls.clear()
            page.update()
            return False

        if generaciones >= MAX_GENERACIONES:
            actualizar_limite()
            page.update()
            return False

        alerta_error.visible = False
        if gestionar_carga:
            actualizar_carga(True, "Componiendo la rima...")
        else:
            mensaje.value = "Componiendo la rima..."
            page.update()
        boton_me_gusta.disabled = True
        boton_no_me_gusta.disabled = True
        poema.controls.clear()
        page.update()

        try:
            # Ejecuta la llamada bloqueante sin congelar la interfaz.
            instruccion = instruccion_rima or INSTRUCCION
            nivel_humor = int(humor.value)
            estilo_seleccionado = nombre_estilo()
            intensidad_humor = {
                1: "humor casi nulo y muy sutil",
                2: "humor ligero y discreto",
                3: "humor moderado",
                4: "humor marcado y frecuente",
                5: "humor muy alto, ingenioso y presente en los cuatro versos",
            }[nivel_humor]
            if archivos_multimedia:
                instruccion += (
                    "\n\nAnaliza conjuntamente los archivos adjuntos: usa "
                    "la imagen como inspiración visual y trata el audio como "
                    "la instrucción hablada del usuario para el estilo, tono "
                    "o enfoque. Prioriza el estilo o indicación específica "
                    "del audio; si no se menciona un estilo, usa "
                    f"{estilo_seleccionado}. Conserva el tema de la imagen "
                    "y escribe exactamente cuatro versos originales. "
                    f"Nivel de humor orientativo: {nivel_humor}/5 "
                    f"({intensidad_humor})."
                )
            else:
                instruccion += (
                    f"\n\nEstilo seleccionado: {estilo_seleccionado} "
                    f"({estilo.value}). "
                    f"Aplica estrictamente sus rasgos: "
                    f"{DETALLE_ESTILOS[estilo.value]}. Mantén su vocabulario, "
                    "ritmo, cadencia y métrica de principio a fin; no mezcles "
                    "géneros ni estilos. En el campo JSON \"estilo\", escribe "
                    f"exactamente \"{estilo_seleccionado}\". "
                    f"Nivel de humor seleccionado: {nivel_humor}/5 "
                    f"({intensidad_humor}). Ajusta el humor a ese nivel sin "
                    "sacrificar la rima ni la naturalidad."
                )
            rimas_anteriores = historial + (
                [rima_actual] if rima_actual is not None else []
            )
            if rimas_anteriores:
                contexto = "\n".join(
                    f"- {rima['titulo']}: "
                    + " / ".join(
                        rima[f"verso{numero}"] for numero in range(1, 5)
                    )
                    for rima in rimas_anteriores[-5:]
                )
                instruccion += (
                    "\n\nUsa estas rimas anteriores solo como contexto para "
                    "mantener coherencia. No repitas sus títulos ni versos "
                    "literalmente:\n"
                    f"{contexto}"
                )
            generaciones += 1
            actualizar_limite()
            page.update()
            if archivos_multimedia:
                respuesta = await asyncio.to_thread(
                    ia_multimedia,
                    instruccion,
                    archivos_multimedia,
                    texto=texto,
                    como_json=True,
                )
            else:
                respuesta = await asyncio.to_thread(
                    ia, instruccion, texto, como_json=True
                )
            campos = ("titulo", "verso1", "verso2", "verso3", "verso4", "estilo")
            if not isinstance(respuesta, dict) or any(
                not isinstance(respuesta.get(campo), str)
                or not respuesta[campo].strip()
                for campo in campos
            ):
                raise ValueError("La respuesta JSON no tiene todos los campos.")

            nueva_rima = {
                campo: respuesta[campo].strip()
                for campo in campos
            }
            if rima_actual is not None:
                historial.append(rima_actual)
                del historial[:-5]
            rima_actual = nueva_rima
            calificacion_actual = None
            poema.controls.extend(tarjetas_rima(rima_actual))
            actualizar_historial()
            boton_copiar.disabled = False
            boton_escuchar.disabled = False
            boton_me_gusta.disabled = False
            boton_no_me_gusta.disabled = False
            mensaje_calificacion.value = ""
            mensaje.value = ""
            return True
        except RuntimeError as error:
            mostrar_alerta("No se pudo crear la rima", explicar_error(error))
        except ValueError:
            mostrar_alerta(
                "La respuesta no se pudo interpretar",
                "El servicio devolvió un resultado inesperado. Inténtalo "
                "de nuevo con otro tema.",
            )
        except Exception as error:
            mostrar_alerta(
                "No se pudo crear la rima",
                explicar_error(error),
            )
        finally:
            if gestionar_carga:
                actualizar_carga(False)
            else:
                page.update()

    async def copiar_rima(_):
        if rima_actual is None:
            return

        texto_rima = "\n".join(
            [
                rima_actual["titulo"],
                f"Estilo: {rima_actual['estilo']}",
                *(rima_actual[f"verso{numero}"] for numero in range(1, 5)),
            ]
        )
        try:
            await portapapeles.set(texto_rima)
            snackbar_copiado.open = True
            page.update()
        except Exception:
            snackbar_copiado.content = "No se pudo copiar la rima al portapapeles."
            snackbar_copiado.open = True
            page.update()

    async def escuchar_rima(_):
        if rima_actual is None:
            return

        texto_rima = "\n".join(
            [rima_actual["titulo"]]
            + [rima_actual[f"verso{numero}"] for numero in range(1, 5)]
        )
        # Codifica el texto para que nunca se interprete como código JavaScript.
        texto_codificado = base64.b64encode(
            texto_rima.encode("utf-8")
        ).decode("ascii")
        documento = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Escuchar rima</title>
  <style>
    body {{ background: #212121; color: #fff; font: 18px sans-serif;
           margin: 2rem auto; max-width: 42rem; padding: 0 1rem; }}
    button {{ background: #00acc1; border: 0; border-radius: 8px;
             color: #fff; cursor: pointer; font: inherit; padding: 0.8rem 1rem; }}
    pre {{ line-height: 1.7; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Tu rima</h1>
  <pre id="rima"></pre>
  <button type="button" id="reproducir">Escuchar Rima</button>
  <p id="aviso" role="status" aria-live="polite"></p>
  <script>
    const bytes = Uint8Array.from(atob("{texto_codificado}"),
      caracter => caracter.charCodeAt(0));
    const rima = new TextDecoder().decode(bytes);
    document.getElementById("rima").textContent = rima;
    function reproducir() {{
      if (!("speechSynthesis" in window)) {{
        document.getElementById("aviso").textContent =
          "Este navegador no admite síntesis de voz.";
        return;
      }}
      window.speechSynthesis.cancel();
      const voz = new SpeechSynthesisUtterance(rima);
      voz.lang = "es-ES";
      const voces = window.speechSynthesis.getVoices();
      voz.voice = voces.find(opcion => opcion.lang.toLowerCase().startsWith("es"))
        || null;
      document.getElementById("aviso").textContent = "";
      window.speechSynthesis.speak(voz);
    }}
    document.getElementById("reproducir").addEventListener("click", reproducir);
    window.addEventListener("load", reproducir);
  </script>
</body>
</html>"""
        url_reproductor = (
            "data:text/html;charset=utf-8," + quote(documento, safe="")
        )
        try:
            mensaje.value = "Abriendo la reproducción de voz..."
            page.update()
            await lanzador_url.launch_url(
                url_reproductor,
                web_only_window_name="_blank",
            )
            mensaje.value = ""
        except Exception:
            mensaje.value = (
                "No pude abrir la reproducción. Inténtalo en un navegador "
                "compatible con síntesis de voz."
            )
        finally:
            page.update()

    async def crear_rima(_):
        await generar_rima((tema.value or "").strip())

    async def finalizar_rima_foto_voz():
        nonlocal grabando, grabacion_combinada, imagen_combinada, tarea_limite
        if not grabacion_combinada:
            return

        grabando = False
        grabacion_combinada = False
        tarea = tarea_limite
        tarea_limite = None
        if tarea is not None and tarea is not asyncio.current_task():
            tarea.cancel()

        boton_foto_voz.content = "Rima con foto + voz"
        actualizar_carga(True, "Preparando la foto y la instrucción hablada...")
        try:
            await grabadora.stop_recording()
            pcm = b"".join(trozos_audio)
            trozos_audio.clear()
            imagen = imagen_combinada
            imagen_combinada = None
            if imagen is None:
                mostrar_alerta(
                    "No se encontró la foto",
                    "Selecciona la imagen otra vez y vuelve a grabar la instrucción.",
                )
                return
            if not pcm:
                mensaje.value = (
                    "No se recibió audio. Repite el proceso y dicta tu instrucción."
                )
                page.update()
                return

            wav = pcm_a_wav(pcm, tasa=16000, canales=1)
            instruccion = (
                f"{INSTRUCCION} Usa la imagen adjunta como tema visual y "
                "el audio adjunto como la instrucción hablada para orientar "
                "el estilo o enfoque. Devuelve únicamente el JSON solicitado."
            )
            texto_contexto = (
                "Genera una rima de cuatro versos basándote conjuntamente "
                "en la imagen y la instrucción hablada."
            )
            await generar_rima(
                texto_contexto,
                instruccion,
                gestionar_carga=False,
                archivos_multimedia=[
                    (imagen[0], imagen[1]),
                    (wav, "audio/wav"),
                ],
            )
        except Exception as error:
            mostrar_alerta(
                "No se pudo crear la rima con foto y voz",
                explicar_error(error),
            )
        finally:
            grabando = False
            grabacion_combinada = False
            imagen_combinada = None
            boton_foto_voz.content = "Rima con foto + voz"
            trozos_audio.clear()
            actualizar_carga(False)

    async def crear_rima_desde_foto_y_voz(_):
        nonlocal grabando, grabacion_combinada, imagen_combinada, tarea_limite
        if grabacion_combinada:
            await finalizar_rima_foto_voz()
            return
        if generaciones >= MAX_GENERACIONES:
            actualizar_limite()
            mensaje.value = (
                f"Alcanzaste el límite de {MAX_GENERACIONES} rimas de esta sesión."
            )
            page.update()
            return
        if grabando:
            mensaje.value = (
                "Detén primero la grabación de voz antes de iniciar el modo "
                "de foto y voz."
            )
            page.update()
            return
        if not conexion_segura():
            mensaje.value = (
                "Para usar el micrófono, abre la app con HTTPS. "
                "En desarrollo también funciona en localhost."
            )
            page.update()
            return

        actualizar_carga(True, "Selecciona una foto para inspirar la rima...")
        try:
            archivos = await selector.pick_files(
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not archivos:
                return

            foto = archivos[0]
            datos = foto.bytes
            mime = mimetypes.guess_type(foto.name)[0] or "image/jpeg"
            if (
                not isinstance(datos, bytes)
                or not datos
                or not mime.startswith("image/")
            ):
                mostrar_alerta(
                    "No se pudo leer la foto",
                    "Elige un archivo de imagen válido e inténtalo de nuevo.",
                )
                return
            if not await grabadora.has_permission():
                mensaje.value = (
                    "Permite el acceso al micrófono para dictar la instrucción."
                )
                page.update()
                return

            trozos_audio.clear()
            imagen_combinada = (datos, mime, foto.name)
            iniciado = await grabadora.start_recording()
            if not iniciado:
                imagen_combinada = None
                mensaje.value = (
                    "No se pudo iniciar el micrófono. Revisa los permisos "
                    "del navegador."
                )
                page.update()
                return

            grabando = True
            grabacion_combinada = True
            nombre_foto.value = f"Imagen para la rima: {foto.name}"
            boton_foto_voz.content = "Detener y crear rima"
            actualizar_carga(
                True,
                "Foto lista. Dicta tu estilo o instrucción y pulsa "
                "«Detener y crear rima» cuando termines (máximo 30 segundos).",
                permitir_detener=True,
            )
            tarea_limite = asyncio.create_task(detener_por_limite())
        except Exception as error:
            imagen_combinada = None
            mostrar_alerta(
                "No se pudo iniciar la experiencia de foto y voz",
                explicar_error(error),
            )
        finally:
            if not grabacion_combinada:
                actualizar_carga(False)

    async def crear_rima_desde_foto(_):
        actualizar_carga(True, "Selecciona una imagen...")
        try:
            archivos = await selector.pick_files(
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not archivos:
                return

            foto = archivos[0]
            datos = foto.bytes
            if not isinstance(datos, bytes) or not datos:
                mensaje.value = "No pude leer la imagen seleccionada."
                page.update()
                return

            nombre_foto.value = f"Imagen: {foto.name}"
            mensaje.value = "Leyendo el texto de la imagen..."
            texto_leido_imagen.value = ""
            poema.controls.clear()
            page.update()

            instruccion_imagen = (
                "Extrae literalmente solo el texto explícito y legible de la "
                "imagen (por ejemplo, un letrero, apunte o frase). No inventes "
                "ni completes palabras ilegibles. Devuelve únicamente el "
                "texto extraído, sin comentarios."
            )
            # Primero extrae el texto; su longitud se valida antes de pedir la rima.
            texto_leido = await asyncio.to_thread(
                ia_media,
                instruccion_imagen,
                datos,
                "image/jpeg",
            )
            texto_leido = (
                texto_leido.strip() if isinstance(texto_leido, str) else ""
            )
            if not texto_leido:
                poema.controls.clear()
                mensaje.value = (
                    "No encontré texto legible en la imagen. Prueba con una "
                    "foto más clara y cercana."
                )
                page.update()
                return
            if len(texto_leido) > 500:
                mensaje.value = (
                    f"El texto de la imagen tiene {len(texto_leido)} caracteres; "
                    "el máximo permitido es 500."
                )
                texto_leido_imagen.value = texto_leido
                page.update()
                return
            texto_leido = validar_entrada(texto_leido)
            if texto_leido is None:
                return
            texto_leido_imagen.value = texto_leido
            instruccion_imagen_rima = (
                f"{INSTRUCCION} Compón los versos para que rimen con esta "
                f"frase leída de la imagen: {texto_leido!r}. "
            )
            await generar_rima(
                texto_leido,
                instruccion_imagen_rima,
                gestionar_carga=False,
            )
        except Exception as error:
            mostrar_alerta(
                "No se pudo procesar la imagen",
                explicar_error(error),
            )
            page.update()
        finally:
            actualizar_carga(False)

    async def crear_rima_desde_texto(_):
        actualizar_carga(True, "Selecciona un archivo de texto...")
        try:
            archivos = await selector.pick_files(
                allowed_extensions=["txt"],
                file_type=ft.FilePickerFileType.CUSTOM,
                with_data=True,
            )
            if not archivos:
                return

            archivo = archivos[0]
            contenido = archivo.bytes
            if not isinstance(contenido, bytes) or not contenido:
                mensaje.value = "El archivo está vacío o no se pudo leer."
                page.update()
                return

            documento = contenido.decode("utf-8").strip()
            if not documento:
                mensaje.value = "El archivo no contiene texto para inspirar la rima."
                page.update()
                return

            # El recuento se calcula en Python antes de enviar el texto a la IA.
            recuento = len(documento.split())
            info_documento.value = (
                f"Documento: {archivo.name} · {recuento} palabras"
            )
            instruccion_documento = (
                "Resume o toma inspiración del documento proporcionado para "
                "componer una rima original de exactamente cuatro versos. "
                f"Usa el estilo musical {estilo.value}. {INSTRUCCION}"
            )
            await generar_rima(
                documento,
                instruccion_documento,
                gestionar_carga=False,
            )
        except UnicodeDecodeError:
            mensaje.value = (
                "No pude leer el archivo como UTF-8. Guarda el documento con "
                "codificación UTF-8 e inténtalo de nuevo."
            )
            page.update()
        except Exception as error:
            mostrar_alerta(
                "No se pudo procesar el archivo",
                explicar_error(error),
            )
            page.update()
        finally:
            actualizar_carga(False)

    def conexion_segura():
        # Los navegadores solo permiten usar el micrófono en HTTPS o localhost.
        if not page.web:
            return True
        url = page.url or ""
        try:
            partes = urlsplit(url)
            host = (partes.hostname or "").casefold()
            return partes.scheme == "https" or host in {
                "localhost",
                "127.0.0.1",
                "::1",
            }
        except ValueError:
            return False

    async def detener_y_transcribir():
        nonlocal grabando, tarea_limite
        if not grabando:
            return

        grabando = False
        tarea = tarea_limite
        tarea_limite = None
        if tarea is not None and tarea is not asyncio.current_task():
            tarea.cancel()

        boton_microfono.text = "Grabar voz"
        actualizar_carga(True, "Transcribiendo...")
        try:
            await grabadora.stop_recording()
            pcm = b"".join(trozos_audio)
            trozos_audio.clear()
            if not pcm:
                mensaje.value = "No se recibió audio. Inténtalo de nuevo."
                return

            wav = pcm_a_wav(pcm, tasa=16000, canales=1)
            transcripcion = await asyncio.to_thread(
                ia_media,
                INSTRUCCION_TRANSCRIPCION,
                wav,
                "audio/wav",
            )
            texto = transcripcion.strip() if isinstance(transcripcion, str) else ""
            if not texto:
                mensaje.value = (
                    "No pude entender el audio. Inténtalo de nuevo o escribe el tema."
                )
                page.update()
                return

            texto = validar_entrada(texto)
            if texto is None:
                return

            tema.value = texto
            await generar_rima(texto, gestionar_carga=False)
        except Exception as error:
            mostrar_alerta(
                "No se pudo transcribir el audio",
                explicar_error(error),
            )
            page.update()
        finally:
            boton_microfono.text = "Grabar voz"
            actualizar_carga(False)

    async def detener_por_limite():
        await asyncio.sleep(30)
        if grabacion_combinada:
            await finalizar_rima_foto_voz()
        else:
            await detener_y_transcribir()

    async def grabar_voz(_):
        nonlocal grabando, tarea_limite
        if grabando:
            await detener_y_transcribir()
            return

        if not conexion_segura():
            mensaje.value = (
                "Para usar el micrófono, abre la app con HTTPS. "
                "En desarrollo también funciona en localhost."
            )
            page.update()
            return

        actualizar_carga(True, "Solicitando acceso al micrófono...")
        try:
            if not await grabadora.has_permission():
                mensaje.value = (
                    "Permite el acceso al micrófono en el navegador para dictar el tema."
                )
                actualizar_carga(False)
                return

            trozos_audio.clear()
            iniciado = await grabadora.start_recording()
            if not iniciado:
                mensaje.value = (
                    "No se pudo iniciar la grabación. Revisa el permiso del micrófono."
                )
                actualizar_carga(False)
                return

            grabando = True
            boton_microfono.text = "Detener grabación"
            mensaje.value = "Grabando..."
            actualizar_carga(True, permitir_detener=True)
            tarea_limite = asyncio.create_task(detener_por_limite())
        except Exception:
            grabando = False
            boton_microfono.text = "Grabar voz"
            mensaje.value = (
                "No pude iniciar el micrófono. Verifica los permisos y que la app use HTTPS."
            )
            actualizar_carga(False)

    boton.on_click = crear_rima
    boton_copiar.on_click = copiar_rima
    boton_escuchar.on_click = escuchar_rima
    boton_microfono.on_click = grabar_voz
    boton_foto.on_click = crear_rima_desde_foto
    boton_foto_voz.on_click = crear_rima_desde_foto_y_voz
    boton_texto.on_click = crear_rima_desde_texto
    boton_me_gusta.on_click = calificar_positivamente
    boton_no_me_gusta.on_click = calificar_negativamente
    humor.on_change = actualizar_humor
    return vista_app
