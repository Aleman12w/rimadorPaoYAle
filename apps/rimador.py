import asyncio
from urllib.parse import urlsplit

import flet as ft
from flet_audio_recorder import (
    AudioEncoder,
    AudioRecorder,
    AudioRecorderConfiguration,
)

from ia import ia
from multimedia import ia_media, pcm_a_wav


INSTRUCCION = (
    "Escribe una rima original sobre el tema indicado, formada exactamente "
    "por cuatro versos. Los versos deben tener ritmo y rima entre sí, ser "
    "naturales y apropiados. Devuelve únicamente un objeto JSON con la clave "
    "\"versos\", cuyo valor sea una lista de exactamente cuatro cadenas."
)

INSTRUCCION_TRANSCRIPCION = (
    "Transcribe únicamente las palabras que dice la persona en el audio. "
    "Devuelve la transcripción en español, sin explicaciones ni comillas."
)


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
        ],
        border_color=ft.Colors.CYAN_400,
        focused_border_color=ft.Colors.CYAN,
        label_style=ft.TextStyle(color=ft.Colors.CYAN_200),
        text_style=ft.TextStyle(color=ft.Colors.WHITE),
        expand=True,
    )
    mensaje = ft.Text(color=ft.Colors.CYAN_200)
    versos = ft.Column(spacing=10)
    boton = ft.Button(
        "Crear rima",
        bgcolor=ft.Colors.CYAN_700,
        color=ft.Colors.WHITE,
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

    vista_app = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "Rimador",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.CYAN_300,
                ),
                ft.Text(
                    "Dame un tema y crearé una rima de cuatro versos.",
                    color=ft.Colors.GREY_300,
                ),
                tema,
                estilo,
                boton_foto,
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
                progreso,
                mensaje,
                versos,
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
        boton.disabled = cargando
        boton_foto.disabled = cargando
        boton_texto.disabled = cargando
        boton_microfono.disabled = cargando and not permitir_detener
        progreso.visible = cargando
        if texto is not None:
            mensaje.value = texto
        page.update()

    def validar_entrada(texto):
        texto = (texto or "").strip()
        if not texto:
            mensaje.value = "La entrada está vacía. Escribe o carga un tema."
            page.update()
            return None
        if len(texto) > 500:
            mensaje.value = (
                f"La entrada tiene {len(texto)} caracteres; el máximo permitido es 500."
            )
            page.update()
            return None
        return texto

    async def generar_rima(texto, instruccion_rima=None, gestionar_carga=True):
        texto = validar_entrada(texto)
        if texto is None:
            versos.controls.clear()
            page.update()
            return False

        if gestionar_carga:
            actualizar_carga(True, "Componiendo la rima...")
        else:
            mensaje.value = "Componiendo la rima..."
            page.update()
        versos.controls.clear()
        page.update()

        try:
            # Ejecuta la llamada bloqueante sin congelar la interfaz.
            instruccion = instruccion_rima or (
                f"{INSTRUCCION} Usa el estilo musical {estilo.value}."
            )
            respuesta = await asyncio.to_thread(
                ia, instruccion, texto, como_json=True
            )
            lineas = respuesta.get("versos") if isinstance(respuesta, dict) else None
            if (
                not isinstance(lineas, list)
                or len(lineas) != 4
                or any(not isinstance(linea, str) or not linea.strip() for linea in lineas)
            ):
                raise ValueError("La respuesta no contiene cuatro versos.")

            # Python numera los versos para mantener el formato consistente.
            versos.controls.extend(
                ft.Row(
                    controls=[
                        ft.Text(
                            f"{numero}.",
                            color=ft.Colors.CYAN_300,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(linea.strip(), color=ft.Colors.WHITE, expand=True),
                    ],
                    spacing=10,
                )
                for numero, linea in enumerate(lineas, start=1)
            )
            mensaje.value = ""
            return True
        except RuntimeError as error:
            detalle = str(error).casefold()
            if "api key not valid" in detalle or "invalid api key" in detalle:
                mensaje.value = (
                    "La clave de Gemini no es válida. Configura una clave "
                    "correcta en GEMINI_API_KEY y vuelve a intentarlo."
                )
            elif "falta gemini_api_key" in detalle:
                mensaje.value = (
                    "Falta configurar GEMINI_API_KEY con una clave de Gemini."
                )
            elif "http 429" in detalle:
                mensaje.value = (
                    "Gemini recibió demasiadas solicitudes. Espera un momento "
                    "y vuelve a intentarlo."
                )
            else:
                mensaje.value = (
                    "No pude crear la rima. Revisa la conexión y la "
                    "configuración de Gemini e inténtalo de nuevo."
                )
        except Exception:
            # Muestra un aviso sencillo sin exponer detalles técnicos.
            mensaje.value = (
                "No pude crear la rima. Inténtalo de nuevo en un momento."
            )
        finally:
            if gestionar_carga:
                actualizar_carga(False)
            else:
                page.update()

    async def crear_rima(_):
        await generar_rima((tema.value or "").strip())

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
            versos.controls.clear()
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
                versos.controls.clear()
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
                f"Usa el estilo musical {estilo.value}."
            )
            await generar_rima(
                texto_leido,
                instruccion_imagen_rima,
                gestionar_carga=False,
            )
        except Exception:
            mensaje.value = (
                "No pude leer el texto o crear la rima con esa imagen. "
                "Inténtalo de nuevo con una foto más clara."
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
                "Usa el estilo musical "
                f"{estilo.value}. Devuelve únicamente un objeto JSON con la "
                "clave \"versos\", cuyo valor sea una lista de exactamente "
                "cuatro cadenas."
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
        except Exception:
            mensaje.value = (
                "No pude procesar el archivo de texto. Inténtalo de nuevo."
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
        except Exception:
            mensaje.value = (
                "No pude transcribir el audio. Revisa la conexión y vuelve a intentarlo."
            )
            page.update()
        finally:
            boton_microfono.text = "Grabar voz"
            actualizar_carga(False)

    async def detener_por_limite():
        await asyncio.sleep(30)
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
    boton_microfono.on_click = grabar_voz
    boton_foto.on_click = crear_rima_desde_foto
    boton_texto.on_click = crear_rima_desde_texto
    return vista_app
